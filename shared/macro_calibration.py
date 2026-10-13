"""shared/macro_calibration.py — macro_thresholds.json loader SSOT(S-GRAY-1 v18.244)

從 L2 `macro_helpers.py`(屬「純函式 / 無 I/O」)下沉至 L0 Infra(config loader 屬
cross-cutting 基礎建設)。修復 CLAUDE.md §8.3 灰色地帶:
「`macro_helpers.py`:分類 L2 但有輕度 I/O(讀 `macro_thresholds.json`)→ 該抽 config-loader 到 L0」。

對外 API:
- `HEALTH_DEFENSE_THRESHOLD_DEFAULT` / `BULL_MIN_SCORE_DEFAULT`:json 缺檔 / 越界時 fallback
- `load_calibrated_thresholds()`:讀 json 回 `(HEALTH_DEFENSE_THRESHOLD, BULL_MIN_SCORE)` tuple
- `read_calibration_meta()`(批 Z54):診斷顯示用的**檔內原值**唯讀快照(門檻值 + last_calibrated + method),
  **任何異常一律 raise**(與上一支的靜默退回刻意不同);**不**代表此刻生效值(見該函式 docstring)

caller(`macro_helpers.py`)在 module-level 一次性呼叫,賦值給原 module-level 常數,
向後相容介面 0 改(caller import path 改 + module 內常數值來源改,API 不變)。

設計:純檔 I/O 模組,僅 `json` + `os` std lib 依賴,**無**外部 HTTP / streamlit / pandas。
"""
from __future__ import annotations
import json as _json
import os as _os
from dataclasses import dataclass
from typing import Optional, Tuple

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


# ══════════════════════════════════════════════════════════════════
# 唯讀 metadata（批 Z54）—— 給「📖 憑什麼 › 進階診斷 › 門檻校準」卡顯示用
# ══════════════════════════════════════════════════════════════════
#: 檔名（顯示用；⛔ 不把完整路徑上畫面）。
CALIBRATION_FILENAME: str = _os.path.basename(_CALIBRATION_PATH)

#: `read_calibration_meta()` 要求檔內**一定要有**的四個欄位（缺任一個 ⇒ fail loud）。
CALIBRATION_REQUIRED_KEYS: Tuple[str, ...] = (
    'HEALTH_DEFENSE_THRESHOLD', 'BULL_MIN_SCORE', 'last_calibrated', 'method')


@dataclass(frozen=True)
class CalibrationMeta:
    """`macro_thresholds.json` 的**檔內原值**唯讀快照。

    ⚠️ **這是「檔裡寫的」，不是「判燈程式此刻實際使用的」**：判燈用的是
    L2 `compute.macro.macro_helpers.HEALTH_DEFENSE_THRESHOLD / BULL_MIN_SCORE`，
    它們在 import 時經 `load_calibrated_thresholds()` 載入一次（越界／壞檔會靜默退回預設，
    檔案之後被改也不會跟著變）。兩者是否一致由 L3
    `services.calibration_status_service` 比對，本模組（L0）不碰 L2。

    Attributes:
        health_defense_threshold / bull_min_score: 檔內原值（整數；型別不對 ⇒ raise）。
        last_calibrated: 檔內原值。`None` ＝ JSON `null`（從未校準）—— ⛔ 不代換成任何說法。
        method: 檔內原值（例：`"default (uncalibrated)"`）。`None` ＝ JSON `null`。
    """

    health_defense_threshold: int
    bull_min_score: int
    last_calibrated: Optional[str]
    method: Optional[str]


def read_calibration_meta() -> CalibrationMeta:
    """讀 `macro_thresholds.json` 的檔內原值。**純讀；任何異常一律 raise**（§1）。

    與 `load_calibrated_thresholds()` 的分工（⚠️ 刻意不同）：
      · 那一支是**判燈用**的 production loader —— 缺檔／壞檔／越界一律**靜默**退回預設值，
        理由寫在它的 docstring（L0 跨層失敗會牽動全棧）。**行為本批一字未動。**
      · 本函式是**診斷顯示用** —— 只回答「檔裡寫了什麼」，所以**不吞任何異常**：
        缺檔 → `FileNotFoundError`、壞 JSON → `json.JSONDecodeError`、
        頂層不是物件／缺欄位／型別不對 → `ValueError`。
      · ⛔ 本函式**不**判斷檔內值是不是此刻生效的值 —— 那要拿 L2 的執行中常數比，
        由 L3 `services.calibration_status_service.get_calibration_status()` 做。
    """
    with open(_CALIBRATION_PATH, 'r', encoding='utf-8') as _f:
        _cfg = _json.load(_f)
    if not isinstance(_cfg, dict):
        raise ValueError(
            f'{CALIBRATION_FILENAME} 的頂層不是物件（實際 {type(_cfg).__name__}）')
    _missing = [_k for _k in CALIBRATION_REQUIRED_KEYS if _k not in _cfg]
    if _missing:
        raise ValueError(f'{CALIBRATION_FILENAME} 缺欄位：{_missing}')
    for _k in ('last_calibrated', 'method'):
        if _cfg[_k] is not None and not isinstance(_cfg[_k], str):
            raise ValueError(
                f'{CALIBRATION_FILENAME} 的 {_k} 應為字串或 null（實際 {type(_cfg[_k]).__name__}）')
    _vals = []
    for _k in ('HEALTH_DEFENSE_THRESHOLD', 'BULL_MIN_SCORE'):
        _v = _cfg[_k]
        if isinstance(_v, bool) or not isinstance(_v, int):
            raise ValueError(
                f'{CALIBRATION_FILENAME} 的 {_k} 應為整數（實際 {_v!r}）')
        _vals.append(_v)
    return CalibrationMeta(
        health_defense_threshold=_vals[0],
        bull_min_score=_vals[1],
        last_calibrated=_cfg['last_calibrated'],
        method=_cfg['method'])
