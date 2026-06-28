"""src/config/ — L0 全域常數聚合(v18.360 Phase 2 F-6.1)。

Re-export 4 個原 root L0 config module 公開 names,讓 caller 寫:
    from src.config import RSI_OVERBOUGHT, PRIORITY, TAIWAN_ADVISOR_PERSONA, get_stock_name

而非冗餘的 `from src.config.config import RSI_OVERBOUGHT`。

無命名衝突(F-6.1 動工前已 grep 全 4 檔 top-level public names 驗證)。
公開 names 範圍:
  config       — 市場閾值 / 均線 / 風控 / 評分曲線
  data_config  — 來源優先順序 PRIORITY / TTL / PKL_DIR
  persona      — TAIWAN_ADVISOR_PERSONA AI 人設提示詞
  stock_names  — get_stock_name(), refresh_name_cache()
"""
from .config import *  # noqa: F401,F403
from .data_config import *  # noqa: F401,F403
from .persona import *  # noqa: F401,F403
from .stock_names import *  # noqa: F401,F403
