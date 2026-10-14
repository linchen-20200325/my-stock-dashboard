"""個股六因子健康分的「因子名 ＋ 配分」SSOT（批 Z55，2026-10-13）。

收什麼：L2 `src/compute/scoring/scoring_helpers.calc_health_score` 六個因子各自的
**滿分（配分）**，以及六項合計（＝ 該函式的分數上限）。

⛔ 不收：
  · 各因子**內部的分段給分**（例：趨勢「多箱整理 18」、RSI「中性偏弱 12」）——
    那是每個因子自己的評分曲線，不是配分，仍留在 L2 函式內。
  · 等第分界（A／B 級下界）—— 那在 `shared/health_thresholds.py`，是另一件事：
    分界說「幾分算好」，本表說「這幾分怎麼分配到六個因子」。
  · 總經 health（`shared/position_throttle.py` 的油門切點）—— 不同尺度的量。

值的出處（§3.3 provenance）：本表建立當下（2026-10-13）逐值取自 `calc_health_score`
**程式實際使用的值**（每個因子 `details[...]` 的第三欄與滿分給分），不是取自註解：
趨勢 30 · RSI 20 · 量比 15 · IBS 10 · KD 15 · 布林 10，合計 100。
建表時 L2 改讀本表，並以 `tests/test_batch_z55.py` 的 golden test 釘住「改讀前後
`calc_health_score` 對同一組輸入逐值相同」。

因子名＝`calc_health_score` 回傳的 `details` 字典的 key（程式本來就用的名字，⛔ 不另取）。

設計：純常數模組，零 import 依賴（L0）。
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping

#: `((因子名, 配分), …)`，順序＝`calc_health_score` 內的計分順序。
HEALTH_SCORE_FACTORS: Final[tuple[tuple[str, int], ...]] = (
    ("趨勢", 30),
    ("RSI", 20),
    ("量比", 15),
    ("IBS", 10),
    ("KD", 15),
    ("布林", 10),
)

#: 因子名 → 配分（唯讀）。
HEALTH_SCORE_FACTOR_POINTS: Final[Mapping[str, int]] = MappingProxyType(
    dict(HEALTH_SCORE_FACTORS))

#: 六項配分合計 ＝ `calc_health_score` 的分數上限。
HEALTH_SCORE_TOTAL: Final[int] = sum(_p for _n, _p in HEALTH_SCORE_FACTORS)

# 建表即對帳（用 raise 不用 assert：`python -O` 會拿掉 assert）。
if len(HEALTH_SCORE_FACTOR_POINTS) != len(HEALTH_SCORE_FACTORS):
    raise RuntimeError("HEALTH_SCORE_FACTORS 有重複的因子名")
if HEALTH_SCORE_TOTAL != 100:
    raise RuntimeError(
        f"六因子配分合計為 {HEALTH_SCORE_TOTAL}，不是 100 —— "
        "`calc_health_score` 的 0~100 尺度與等第分界（health_thresholds）都建立在 100 上")
