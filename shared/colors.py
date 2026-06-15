"""v18.210 K4：traffic-light 顏色 + emoji SSOT 常數模組。

Phase 1 audit 找到 traffic-light hex（#3fb950/#d29922/#f85149）散落 15 檔 110 處 +
舊版 material colors（#00c853/#f44336/#ff9800）4 檔 16 處。本模組提供命名常數
讓改 palette 時改一處生效。

設計：純常數模組，零 import 依賴；caller 用 `from shared.colors import TRAFFIC_*`。

對外 API：
- TRAFFIC_GREEN / TRAFFIC_YELLOW / TRAFFIC_RED：GitHub-style 主用三色
- TRAFFIC_NEUTRAL：⬜ 灰（unknown / disabled）
- 舊版 material aliases（MATERIAL_GREEN/RED/ORANGE）：v18 早期用，留向後相容
- TRAFFIC_EMOJI：emoji 元組（🟢🟡🔴⬜）

不收 emoji 字面（emoji 通常 inline 在文字流，常數化反而難讀）。
"""
from __future__ import annotations

# GitHub-style traffic light（Stock 主用版，v18.197 起鋪開）
TRAFFIC_GREEN: str = "#3fb950"
TRAFFIC_YELLOW: str = "#d29922"
TRAFFIC_RED: str = "#f85149"
TRAFFIC_NEUTRAL: str = "#6e7681"  # 灰，未知/disabled

# 舊版 Material Design colors（v18 早期 health_inspector / financial_health_engine 用）
MATERIAL_GREEN: str = "#00c853"   # 健康成長
MATERIAL_RED: str = "#f44336"     # 吃本金
MATERIAL_ORANGE: str = "#ff9800"  # 邊緣健康

# 同義對應（給 traffic-light 統一參考）
TRAFFIC_EMOJI: tuple[str, str, str, str] = ("🟢", "🟡", "🔴", "⬜")
TRAFFIC_HEX: tuple[str, str, str, str] = (
    TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED, TRAFFIC_NEUTRAL,
)


def emoji_to_hex(emoji: str) -> str:
    """🟢/🟡/🔴/⬜ → traffic-light hex；未知 emoji → TRAFFIC_NEUTRAL。"""
    _m = {"🟢": TRAFFIC_GREEN, "🟡": TRAFFIC_YELLOW,
          "🔴": TRAFFIC_RED, "⬜": TRAFFIC_NEUTRAL}
    return _m.get(emoji, TRAFFIC_NEUTRAL)
