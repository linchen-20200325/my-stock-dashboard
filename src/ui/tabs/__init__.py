"""src/ui/tabs/ — L5 主 Streamlit Tab + 其他渲染元件。PEP 562 `__getattr__` **延遲載入**。

v18.406 U4 Phase 2:新增 `stock_sections/` 子目錄,收 tab_stock.py 拆檔後的
section render 函式(類比 `macro/` 子目錄模式)。

═══ 為什麼從 eager 改成 lazy(2026-09-07,FE-7)═══════════════════════════
本檔原本在 module level 寫 `from . import (tab_edu, tab_macro, tab_stock, ...)`,
**一被 import 就把 15 個子模組連鎖拉進整棵樹**。實測後果(AppTest 實錘,非推論):

    `import src.ui.views.page_today`
      → page_today 的 module-level `from src.ui.tabs.tab_today import ...`
      → Python 先 import 父套件 `src.ui.tabs` → 本檔 eager list 全部執行
      → sys.modules 多出 152 個 `src.*`(含 section_inputs / macro_helpers)+ pandas + plotly

那些模組**任何一個** import 失敗,`page_today` 自己就 import 不起來 → 整頁空白,
且 `page_today.load_macro_readout` 的 try/except 擋不住(它只擋得住**呼叫期**例外,
擋不住 import 期)。改 lazy 後 `import ...page_today` 只會載入 `tab_today` 一條路徑。

⚠️ **這與 `src/data/macro/__init__.py` 檔頭那條「改真 lazy 已評估為 WONTFIX」不衝突**,
   兩者理由**逐條**對照如下(本檔是它點名的例外,不是推翻它):
   · WONTFIX 理由 1「冷啟動淨節省 ≈ 0 ms」—— 本檔的動機**不是**啟動時間,
     是**故障半徑**:讓 A 模組的 import 錯誤不再連坐到 B 模組的 import。
   · WONTFIX 理由 2「import 錯誤會延後落進 caller 的 `except Exception` 被吞掉,違反 §1」
     —— 本檔**不會**發生:`from src.ui.tabs import render_tab_macro` 仍在**同一行**
     raise(只是不再連帶 import 不相干的 14 個模組);少掉的是**別人的**錯誤誤傷,
     不是自己的錯誤被吞。§1 Fail Loud 的表面積**縮小而非變寬**。
   ⚠️ 反過來說,`src/data/macro/` 那條 WONTFIX **依然有效**,不得引用本檔去改它 ——
     那需要各自的實測依據(見 CLAUDE.md §-2 規則 5/6)。

⚠️ 「延遲載入」= submodule 的 import 被延到**第一次真的取用**才發生;
   attribute lookup 本身仍是**即時轉發**(不快取進本 module 的 globals),
   故 `monkeypatch.setattr(submod, 'X', mock)` 對 caller 的 deferred import
   仍然生效(避免 re-export snapshot trap),此性質與 eager 版**完全相同**。
⚠️ 測試若要裝 streamlit stub,**務必在裝之前**先 import 目標
   (見 tests/test_zz_streamlit_pollution_lock.py 第四層守衛)。本檔改 lazy 後,
   stub 視窗內連鎖拉進的模組數大幅下降,但**規則不變** —— lazy 只是縮小
   「首次 import 落在視窗內」的機會,不是消滅它。
"""
import importlib
import importlib.util

# v18.464: tab_etf_margin_simulator 從 UI 移除；v19.159 團隊稽核真刪整功能棧
# (UI + etf_margin_simulator L2 engine + fetch_etf_close_history + 測試),見 docs/ARCHIVED_FEATURES.md

# re-export 來源。**順序 = 符號查找順序**,與改 lazy 前的 eager tuple 逐字相同 ——
# 同名符號出現在多個子模組時的勝者因此不變(零行為變更的關鍵)。
_SUBMODULE_NAMES = (
    "tab_edu", "tab_helpers", "tab_macro", "tab_macro_v2",
    "tab_stock", "tab_stock_grp",
    "tab_stock_picker",
    # F-8 補搬:L5 渲染元件(非單一 tab,但同層性質)
    "chip_radar", "grape_ladder", "hot_money", "macro_classroom", "macro_stock_link",
    "portfolio_linkage", "yield_screener",
    # U4 Phase 2:tab_stock 子目錄
    "stock_sections",
)


def _load(_name):
    """import 本套件的一個子模組並回傳。

    import 成功後 Python 會自動把子模組設成本 module 的屬性,
    故同一個子模組名只會走到這裡一次 —— 之後 `__getattr__` 根本不會被呼叫。
    """
    return importlib.import_module(f".{_name}", __name__)


def __getattr__(name):
    # ① dunder 一律不轉發。`__all__` / `__wrapped__` / `__bases__` 這類來自
    #    pytest / IDE / inspect 的探測若掉進 ③ 的迴圈,會把 15 個子模組全載進來
    #    = 悄悄退化回 eager,延遲載入就白做了。
    if name.startswith("__") and name.endswith("__"):
        raise AttributeError(f"module 'src.ui.tabs' has no attribute {name!r}")

    # ② 名字本身就是子模組 → 只載那一個,不進 ③ 的迴圈。
    #    涵蓋**未列入 re-export** 者(tab_today / tab_ai_chat / tab_sector_flow /
    #    portfolio_binder / portfolio_manager / portfolio_status_bar /
    #    pattern_targets_ui / macro / stock_grp_sections),eager 版靠 Python 的
    #    `from ... import` submodule fallback 才載得到它們,行為等價。
    try:
        _spec = importlib.util.find_spec(f".{name}", __name__)
    except (ImportError, AttributeError, ValueError):
        _spec = None
    if _spec is not None:
        return _load(name)

    # ③ 轉發符號:依 _SUBMODULE_NAMES 順序載入,命中即回。
    #    查找順序與 eager 版相同,差別只在「沒被問到的子模組不會被載入」。
    for _sub_name in _SUBMODULE_NAMES:
        _sub = _load(_sub_name)
        if name in vars(_sub):
            return getattr(_sub, name)
    raise AttributeError(f"module 'src.ui.tabs' has no attribute {name!r}")


def __dir__():
    # 只列「不必 import 就知道」的成員:本 module globals + re-export 子模組名。
    # 轉發符號不列 —— 要列就得把 15 個子模組全載進來,等於毀掉延遲載入。
    return sorted(set(globals()) | set(_SUBMODULE_NAMES))
