"""src/ — v18.360 Phase 2 F-6 啟動目錄樹搬移。

按 §8.2 七層架構,後續子目錄將陸續加入:
  src/config/   (L0 已落地,F-6.1)
  src/data/     (L1,F-6.2 規劃中)
  src/compute/  (L2,F-6.3 規劃中)
  src/services/ (L3,F-6.4 規劃中)
  src/ui/       (L4+L5,F-6.5 規劃中)

本 __init__.py 故意留空(不做頂層 re-export),避免引發循環 import。
caller 應走 `from src.<sub> import X` 取得各層 API。
"""
