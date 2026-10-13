"""L3 Service — 門檻校準的唯讀狀態（批 Z54）。給「📖 憑什麼 › 進階診斷 › 門檻校準」卡。

回答兩件事，**分開回、⛔ 不混**：
  · **此刻實際生效的值**：判燈程式真正在用的 L2 `compute.macro.macro_helpers`
    module 常數 `HEALTH_DEFENSE_THRESHOLD` / `BULL_MIN_SCORE`（import 時經
    `shared.macro_calibration.load_calibrated_thresholds()` 載入一次；越界／壞檔靜默退回預設；
    之後檔案被改也不會跟著變，直到 process 重啟）。
  · **檔裡寫的**：L0 `shared.macro_calibration.read_calibration_meta()`（缺檔／壞檔一律 raise）。
兩者不一致 ⇒ `consistent=False`，由畫面畫成紅卡並寫出兩組值 ——
⛔ 不得拿檔內值冒充生效值（§1 假數字）。

**不做什麼**：⛔ 不重跑校準、⛔ 不寫檔、⛔ 不 import streamlit、零網路。
分層：L3 → L2（讀 module 常數）／L0（讀檔）。皆為下行。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CalibrationStatus:
    """門檻校準的唯讀狀態。

    Attributes:
        effective_health_defense_threshold / effective_bull_min_score: 判燈程式此刻使用的值
            （L2 `macro_helpers` module 常數）。
        file_health_defense_threshold / file_bull_min_score: `macro_thresholds.json` 檔內原值。
        last_calibrated / method: 檔內原值（`None` ＝ JSON `null`，⛔ 不代換）。
    """

    effective_health_defense_threshold: int
    effective_bull_min_score: int
    file_health_defense_threshold: int
    file_bull_min_score: int
    last_calibrated: Optional[str]
    method: Optional[str]

    @property
    def consistent(self) -> bool:
        """檔內值是不是就是此刻生效的值。"""
        return ((self.file_health_defense_threshold, self.file_bull_min_score)
                == (self.effective_health_defense_threshold, self.effective_bull_min_score))


def get_calibration_status() -> CalibrationStatus:
    """讀生效值（L2 常數）與檔內值（L0）。**純讀；讀檔異常照樣 raise**（由畫面轉紅卡）。"""
    from shared.macro_calibration import read_calibration_meta
    from src.compute.macro import macro_helpers as _mh   # L3 → L2（下行，合法）

    _meta = read_calibration_meta()
    return CalibrationStatus(
        effective_health_defense_threshold=int(_mh.HEALTH_DEFENSE_THRESHOLD),
        effective_bull_min_score=int(_mh.BULL_MIN_SCORE),
        file_health_defense_threshold=_meta.health_defense_threshold,
        file_bull_min_score=_meta.bull_min_score,
        last_calibrated=_meta.last_calibrated,
        method=_meta.method)
