"""src/data/macro/ — 總經資料 fetcher。

PEP 562 `__getattr__` 即時轉發：每次 `from src.data.macro import X` lookup 時
從 submodule 即時取 attribute,使 `monkeypatch.setattr(submod, 'X', mock)`
能對 caller 的 deferred / lazy import 生效（避免 re-export snapshot trap）。

⚠️ 「即時轉發」指的是 **attribute lookup 是即時的**,不是 import 被延後。
   下面那行 `from . import (...)` 是**立即執行**的 —— 本 package 一被 import,
   全部 submodule 就都載入了。本 pattern 從來不是為了省啟動時間。
   （舊文案寫「PEP 562 lazy forward」,被讀成「延遲載入」造成過實際事故:
   測試在 streamlit stub 視窗內首次 import 這類 barrel,連鎖拉進的模組
   會永久綁住待丟棄的 stub。改真 lazy 已評估為 WONTFIX —— 實測冷啟動
   淨節省 ≈ 0 ms(Streamlit 每次 rerun 都會跑完所有 tab body),
   卻會讓 import 錯誤延後落進 caller 的 `except Exception` 被吞掉,違反 §1。）
"""
from . import macro_core, tw_macro, leading_indicators, macro_alert, macro_snapshot  # noqa: F401

_SUBMODULES = (macro_core, tw_macro, leading_indicators, macro_alert, macro_snapshot)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.data.macro' has no attribute {name!r}")
