"""src/data/macro/ — 總經資料 fetcher。

PEP 562 `__getattr__` 即時轉發：每次 `from src.data.macro import X` lookup 時
從 submodule 即時取 attribute,使 `monkeypatch.setattr(submod, 'X', mock)`
能對 caller 的 deferred / lazy import 生效（避免 re-export snapshot trap）。

⚠️ 「即時轉發」指的是 **attribute lookup 是即時的**,不是 import 被延後。
   下面那行 `from . import (...)` 是**立即執行**的 —— 本 package 一被 import,
   全部 submodule 就都載入了。本 pattern 從來不是為了省啟動時間。
   （舊文案寫「PEP 562 lazy forward」,被讀成「延遲載入」造成過實際事故:
   測試在 streamlit stub 視窗內首次 import 這類 barrel,連鎖拉進的模組
   會永久綁住待丟棄的 stub。~~改真 lazy 已評估為 WONTFIX —— 實測冷啟動
   淨節省 ≈ 0 ms(Streamlit 每次 rerun 都會跑完所有 tab body),
   卻會讓 import 錯誤延後落進 caller 的 `except Exception` 被吞掉,違反 §1。~~）

⚠️ **2026-09-07 更新:上面那條刪除線是有意識的政策變更,不是漏刪。**
   **決策者:AI 總管**(非 user 明示);**適用範圍:只有 `src/ui/tabs/` 那一個 barrel 改了。**
   **本檔(`src/data/macro/`)與其餘 18 個 barrel 一律維持 eager,本次不動、也不主張該動**
   (CLAUDE.md §-1:沒有實際 bug 觸發就不要碰)。

   **舊理由仍然成立的部分(沒有被推翻,請不要讀成「lazy 一律是好的」)**:
   以「**省開機時間**」為動機的 lazy 化確實沒有價值 —— Streamlit 每次 rerun 都會
   跑完所有 tab body,冷啟動淨節省 ≈ 0 ms 這個實測結論**至今有效**。
   拿「改成 lazy 會比較快」當理由來動任何 barrel,依然應該被駁回。

   **為何 `src/ui/tabs/` 仍然改了(動機不同,是故障半徑不是速度)**:
   實測 `import src.ui.views.page_today` 在 eager 下會拉進 **152 個 `src.*`**
   (經 `page_today` → `src.ui.tabs.tab_today` → 本類 barrel 連鎖),於是**任何一個
   不相干模組** import 失敗,整頁就空白 —— 紅隊 AppTest 實測 `n_markdown=0`
   且例外**未被捕捉**。改 lazy 後降到 **6 個**,同一個故障變成畫面上的紅態
   (`n_markdown=79`,錯誤同時進 stderr)。

   **關於「錯誤會被 `except Exception` 吞掉」這半句 —— 實測未成立**:
   `from src.ui.tabs import X` 在 lazy 下**仍然在同一行 raise**,只是不再連帶
   import 14 個不相干模組;被消掉的是**別人的**錯誤誤傷,不是自己的錯誤被吞。
   §1 Fail Loud 的表面積因此**縮小**而非變寬(eager 未捕捉例外 → 白頁 vs
   lazy 錯誤上畫面 + 上 stderr)。
   ⚠️ 但這句只在 `src/ui/tabs/` 的實測條件下被否證 —— **本檔沒有做過同樣的實測**,
   故對本檔而言它仍是**待驗事項**,不得拿 `src/ui/tabs/` 的結果替本檔背書。
"""
from . import macro_core, tw_macro, leading_indicators, macro_alert, macro_snapshot  # noqa: F401

_SUBMODULES = (macro_core, tw_macro, leading_indicators, macro_alert, macro_snapshot)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.data.macro' has no attribute {name!r}")
