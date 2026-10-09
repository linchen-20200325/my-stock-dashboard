"""批 Z5（2026-10-05）—— C7-n1 ＋ C7-n8 釘子（L5 only：section_state／handlers／section_news_ai）。

C7-n1（v1 §二 拐點面板 6）
────────────────────────────────────────────────────────────────
`render_section_state` 把 NDC 景氣對策（`fetch_ndc_signal_history`）、領先指標
（`fetch_ndc_leading_index`）、外資連續日數（`fetch_foreign_consecutive_days`）的結果存進 session
快取 `_ndc_hist_cache`／`_ndc_li_cache`／`_fi_streak_cache`。修前（origin/main `84c1ca4`）：
  ① 三支失敗時 L1 回的是**帶 `error` 的 dict**（不是 None）→ `if _ndc_h or _ndc_li`／`if _fi_st`
     照樣成立 → 分群明細印「籌碼…：中性」「景氣…：中性」、頭句「（可評估 2/6 群）」，實際一群都
     不可評估；外資「最新一日缺」（`error=None`、`consec_days=None`）同樣被登記。修前這些情境的
     **完整輸出與「三支都可用、都沒觸發訊號」逐字相同**（＝下方 `_GOLDEN_FLAT`）—— 失敗被說成中性。
  ② 失敗 dict 照樣寫進 session 快取 → 同一個 session 之後的 rerun 不再重抓（上游恢復也看不到）。
  ③ `handlers._macro_session_reset` 的清除名單沒有這三個 key → 一鍵更新／強制重抓都清不掉。
修法：只寫**可用**結果（無 `error`、代表值 `score_latest`／`smooth6m`／`consec_days` 為有限數）；
可評估登記用同一判準；三個 key 加進清除名單。畫面只用既有字樣 —— L2 `aggregate_pivot_families`
的「未評估」、既有頭句（「⚪ 拐點資料不足：6 群僅 N 群可評估 → 不宣稱方向」）與「⚠️ 未評估：…」說明。

C7-n8（v1 §十一 AI 裁決 prompt）
────────────────────────────────────────────────────────────────
`外資大小`／`韭菜指數`（`li_latest` 末列）與 `ad_ratio`（`cl_data['adl']` 末列）為 NaN／±inf 時，
`float(...)` 照樣成功、`is not None` 擋不住 → prompt 印「外資期貨淨口數：+nan 口」「韭菜指數（小台法人
空多比）：+nan%」「ADL 漲跌家數比（上漲家數佔全市場 %）：nan%」（±inf 同理）。修法：非有限 → None，
走既有「缺值整行不送」路徑（先例 DL-f1-s16）；⛔ 新增字。規則引擎本來就把非有限值當缺
（`_is_finite_number`），引擎輸出不變。

golden：以 origin/main `84c1ca4`（修前）用同型 harness（假 st＋同一批離線替身）實跑後**寫死** ——
⛔ 在測試裡讀 git、⛔ 由程式反推。正常值的完整輸出與修前逐字相同（`_GOLDEN_*`）。
另：本檔整份放到 84c1ca4 副本上實跑過 —— 正常值與性質那幾支（golden／快取沿用／引擎對 NaN 與缺值同解）
全過，其餘（修復相關）全紅。
harness：`_FakeST` 以 monkeypatch 換掉被測模組的 module-level `st`；L1 fetcher、Gemini、新聞 RSS、
狀態鎖一律換成離線替身。本檔不觸網、不寫檔。slow lane 另以真 Streamlit（AppTest）驗 rerun 行為。
"""
from __future__ import annotations

import copy
import math

import numpy as np
import pandas as pd
import pytest

import src.data.macro.tw_macro as TW
import src.ui.tabs.macro.handlers as H
import src.ui.tabs.macro.section_news_ai as NEWS
import src.ui.tabs.macro.section_state as STATE


# ══════════════════════════════════════════════════════════════════════════
# 假的 streamlit（只記錄文字；未知 API 一律 no-op）
# ══════════════════════════════════════════════════════════════════════════
class _Rerun(Exception):
    """`st.rerun()` 的替身：讓 §十一 裁決流程在 Gemini 回來後乾淨地停下。"""


class _Any:
    """未實作的 st.* 回傳值：可呼叫 / 可 with / falsy（未知 widget = 沒被按）。"""

    def __init__(self, st):
        self._st = st

    def __call__(self, *a, **k):
        return _Any(self._st)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return getattr(self._st, name)      # column.markdown(...) → 同一個記錄器

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __bool__(self):
        return False


class _FakeST:
    _TEXT = ("markdown", "caption", "info", "warning", "success", "error", "write")

    def __init__(self, session_state=None, clicked=()):
        self.session_state = dict(session_state or {})
        self.secrets: dict = {}
        self.out: list[tuple[str, str]] = []
        self._clicked = set(clicked)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name in _FakeST._TEXT:
            def _rec(body="", *a, **k):
                self.out.append((name, str(body)))
                return _Any(self)
            return _rec
        return _Any(self)

    def columns(self, spec, *a, **k):
        return [_Any(self) for _ in range(spec if isinstance(spec, int) else len(spec))]

    def expander(self, label="", *a, **k):
        self.out.append(("expander", str(label)))
        return _Any(self)

    def button(self, label="", key=None, *a, **k):
        return key in self._clicked

    def rerun(self, *a, **k):
        raise _Rerun()


# ══════════════════════════════════════════════════════════════════════════
# C7-n1 —— 測資（L1 回傳形狀，逐欄照 tw_macro 三支 fetcher 的 `result` 初始 dict）
# ══════════════════════════════════════════════════════════════════════════
_TS = "2026-10-05T00:00:00+00:00"
#: `fetch_ndc_signal_history` 失敗出口（兩個 error 字串皆為 L1 原字）
_H_FAIL = {"score_latest": None, "score_prev": None, "score_prev2": None, "trend": [],
           "inflection": "⬜ 資料不足", "date_latest": "", "source": None,
           "error": "FinMind-TBI + dgtw 皆無景氣對策信號資料", "color_latest": None,
           "fetched_at": _TS}
_H_FAIL_SANITY = dict(_H_FAIL, error="景氣對策信號通過 sanity 後資料不足")
#: `fetch_ndc_leading_index` 失敗出口
_LI_FAIL = {"latest": None, "prev": None, "mom": None, "smooth6m": None, "prev_s6m": None,
            "inflection": "⬜ 資料不足", "trend": [], "date_latest": "", "source": None,
            "error": "FinMind-TBI + dgtw 皆無領先指標歷史", "fetched_at": _TS}
_LI_FAIL_MA = dict(_LI_FAIL, error="6M MA 樣本不足")
#: `fetch_foreign_consecutive_days` 失敗出口
_FI_FAIL = {"consec_days": None, "reversed": False, "today_net": None, "prev_streak": None,
            "inflection": "⬜ 資料不足", "date_latest": "", "source": None,
            "error": "FinMind 抓取失敗", "fetched_at": _TS}
#: 外資「最新一日缺」：L1 印 log 後回 `error=None`、各值 None（批 V2 D2-n5 的既有出口）
_FI_LATEST_MISSING = dict(_FI_FAIL, error=None)

#: 可用、且不觸發任何訊號（📊 震盪持平／📊 持平／📊 震盪）
_H_FLAT = {"score_latest": 25, "score_prev": 25, "score_prev2": 25,
           "trend": [24, 25, 26, 25, 25, 25], "inflection": "📊 震盪持平",
           "date_latest": "2026-08-01", "source": "FinMind:TaiwanBusinessIndicator",
           "error": None, "color_latest": "綠燈", "fetched_at": _TS}
_LI_FLAT = {"latest": 101.2, "prev": 101.2, "mom": 0.0, "smooth6m": 0.0, "prev_s6m": 0.0,
            "inflection": "📊 持平", "trend": [0.0] * 8, "date_latest": "2026-08-01",
            "source": "FinMind:TaiwanBusinessIndicator", "error": None, "fetched_at": _TS}
_FI_FLAT = {"consec_days": 2, "reversed": False, "today_net": 1234567, "prev_streak": -1,
            "inflection": "📊 震盪", "date_latest": "2026-10-03", "source": "FinMind",
            "error": None, "fetched_at": _TS}
#: 可用、且各觸發一盞
_H_UP = dict(_H_FLAT, score_latest=26, score_prev=24, score_prev2=25, inflection="🚀 連2月翻多")
_LI_EXP = dict(_LI_FLAT, smooth6m=0.42, prev_s6m=0.31, inflection="🟢 持續擴張")
_FI_SELL = dict(_FI_FLAT, consec_days=-6, prev_streak=3, today_net=-987654,
                inflection="🔴 連6日賣超")
#: 驗收補測（A 組 B1）：與上面三支方向相反的另一組可用值（舊快取＝`_H_UP`／`_LI_EXP`／`_FI_BUY`，
#: 按更新後上游給的新值＝`_H_DOWN`／`_LI_CON`／`_FI_SELL`）。inflection 與 L1 判定式一致。
_H_DOWN = dict(_H_FLAT, score_latest=24, score_prev=26, score_prev2=25, inflection="⚠️ 連2月翻空")
_LI_CON = dict(_LI_FLAT, smooth6m=-0.35, prev_s6m=-0.2, inflection="🔴 持續收縮")
_FI_BUY = dict(_FI_FLAT, consec_days=6, prev_streak=-2, today_net=987654,
               inflection="🟢 連6日買超")

_KEYS = ("_ndc_hist_cache", "_ndc_li_cache", "_fi_streak_cache")


# ══════════════════════════════════════════════════════════════════════════
# C7-n1 —— golden（84c1ca4 實跑寫死）
# ══════════════════════════════════════════════════════════════════════════
#: 84c1ca4 實跑：面板 6 三支皆可用、皆無訊號（NDC 震盪持平／領先 6M 持平／外資震盪）的完整輸出。
#: ⚠️ 84c1ca4 在「三支全部失敗」「外資最新一日缺」「代表值 NaN／±inf／None／缺鍵」等情境的
#:    完整輸出**也是這一份**（失敗被說成中性 —— 本批要修的就是這件事）。
_GOLDEN_FLAT = [
    ('markdown',
     '<div style="margin:34px 0 10px;padding:12px 18px;background:linear-gradient(90deg,#ff7b722b,#ff7b720a,#0d1117);border-left:6px solid #ff7b72;border-radius:0 10px 10px 0;"><span style="font-size:12px;color:#ff7b72;font-weight:700;opacity:0.85;">拐點</span><div style="font-size:18px;font-weight:900;color:#ff7b72;margin-top:2px;">🔮 拐點</div><div style="font-size:12px;color:#8b949e;margin-top:2px;">六大面向 × CPI×Fed 雙頂回落（景氣反轉偵測）</div></div>'),
    ('markdown',
     '<div style="background:#161b22;border-left:4px solid #eab308;border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0;font-size:13px;font-weight:600;color:#eab308;">⚪ 訊號分歧：偏多 0 群 vs 偏空 0 群（可評估 2/6 群），方向待確認</div>'),
    ('caption',
     '趨勢（均線結構）：未評估　位階（乖離率）：未評估　資金（M1B-M2 / 台幣）：未評估　籌碼（外資期貨 / 韭菜 / 外資連續）：中性　景氣（NDC 對策 / 領先指標）：中性　通膨利率（CPI × Fed）：未評估'),
    ('caption',
     '💡 同一群內的訊號（例：外資期貨大空單＋散戶極度看多）源自同一個潛在因子，**群內取最壞、不累加** —— 避免把同一件事數成多份獨立證據而誇大確信度。'),
    ('caption',
     '⚠️ 未評估：趨勢（均線結構）、位階（乖離率）、資金（M1B-M2 / 台幣）、通膨利率（CPI × Fed）（資料未取得 → 已排除於分母外，既不計入偏多也不計入偏空）'),
    ('markdown',
     '##### 📊 拐點詳細分析 — 六大面向 + CPI×Fed 雙頂回落'),
    ('info',
     '尚無足夠資料計算拐點，請點擊「🚀 一鍵更新全部數據」'),
]

#: 84c1ca4 實跑：三支皆可用且各觸發一盞（景氣對策連2月翻多／領先指標持續擴張／外資連續賣超）的完整輸出。
_GOLDEN_SIGNALS = [
    ('markdown',
     '<div style="margin:34px 0 10px;padding:12px 18px;background:linear-gradient(90deg,#ff7b722b,#ff7b720a,#0d1117);border-left:6px solid #ff7b72;border-radius:0 10px 10px 0;"><span style="font-size:12px;color:#ff7b72;font-weight:700;opacity:0.85;">拐點</span><div style="font-size:18px;font-weight:900;color:#ff7b72;margin-top:2px;">🔮 拐點</div><div style="font-size:12px;color:#8b949e;margin-top:2px;">六大面向 × CPI×Fed 雙頂回落（景氣反轉偵測）</div></div>'),
    ('markdown',
     '<div style="background:#161b22;border-left:4px solid #eab308;border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0;font-size:13px;font-weight:600;color:#eab308;">⚪ 訊號分歧：偏多 1 群 vs 偏空 1 群（可評估 2/6 群），方向待確認</div>'),
    ('caption',
     '趨勢（均線結構）：未評估　位階（乖離率）：未評估　資金（M1B-M2 / 台幣）：未評估　籌碼（外資期貨 / 韭菜 / 外資連續）：偏空　景氣（NDC 對策 / 領先指標）：偏多　通膨利率（CPI × Fed）：未評估'),
    ('caption',
     '💡 同一群內的訊號（例：外資期貨大空單＋散戶極度看多）源自同一個潛在因子，**群內取最壞、不累加** —— 避免把同一件事數成多份獨立證據而誇大確信度。'),
    ('caption',
     '⚠️ 未評估：趨勢（均線結構）、位階（乖離率）、資金（M1B-M2 / 台幣）、通膨利率（CPI × Fed）（資料未取得 → 已排除於分母外，既不計入偏多也不計入偏空）'),
    ('markdown',
     '##### 📊 拐點詳細分析 — 六大面向 + CPI×Fed 雙頂回落'),
    ('markdown',
     "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #22c55e;border-radius:8px;padding:8px 10px;margin:3px 0;min-height:54px;display:flex;align-items:center;'><span style='color:#22c55e;font-weight:700;font-size:13px;'>🚀 景氣對策連2月翻多</span></div>"),
    ('markdown',
     "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #22c55e;border-radius:8px;padding:8px 10px;margin:3px 0;min-height:54px;display:flex;align-items:center;'><span style='color:#22c55e;font-weight:700;font-size:13px;'>✅ 領先指標持續擴張</span></div>"),
    ('markdown',
     "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #ef4444;border-radius:8px;padding:8px 10px;margin:3px 0;min-height:54px;display:flex;align-items:center;'><span style='color:#ef4444;font-weight:700;font-size:13px;'>❌ 外資連續賣超</span></div>"),
    ('expander',
     '🔍 拐點六大面向 — 完整訊號明細 + 判斷參考'),
    ('markdown',
     '<div style="background:#0d1117;border-left:3px solid #22c55e;border-radius:0 6px 6px 0;padding:6px 10px;margin:4px 0;"><span style="color:#22c55e;font-weight:600;">🚀 景氣對策連2月翻多</span><br><span style="color:#8b949e;font-size:12px;">分數 24→26 由跌轉升 → 景氣領先翻揚拐點</span></div>'),
    ('markdown',
     '<div style="background:#0d1117;border-left:3px solid #22c55e;border-radius:0 6px 6px 0;padding:6px 10px;margin:4px 0;"><span style="color:#22c55e;font-weight:600;">✅ 領先指標持續擴張</span><br><span style="color:#8b949e;font-size:12px;">6M smoothed change +0.42% 維持正值 → 景氣擴張</span></div>'),
    ('markdown',
     '<div style="background:#0d1117;border-left:3px solid #ef4444;border-radius:0 6px 6px 0;padding:6px 10px;margin:4px 0;"><span style="color:#ef4444;font-weight:600;">❌ 外資連續賣超</span><br><span style="color:#8b949e;font-size:12px;">外資已連 6 日賣超 → 籌碼流出警示</span></div>'),
    ('caption',
     '📖 拐點判斷參考表 → 詳見「策略手冊」Tab'),
]

#: 84c1ca4 實跑：上一格的 `_pivot_signals`（餵 §十一 AI 的那份）。
_GOLDEN_SIGNALS_PIVOTS = [
    ('景氣對策連2月翻多', '🚀', '#22c55e', '分數 24→26 由跌轉升 → 景氣領先翻揚拐點'),
    ('領先指標持續擴張', '✅', '#22c55e', '6M smoothed change +0.42% 維持正值 → 景氣擴張'),
    ('外資連續賣超', '❌', '#ef4444', '外資已連 6 日賣超 → 籌碼流出警示'),
]

#: 驗收補測（A 組 B1）—— 84c1ca4 實跑（全新 session）：三支都是「新」值（`_H_DOWN`／`_LI_CON`／`_FI_SELL`）
#: 的完整輸出。按更新後必須長這樣（不得沿用舊快取 `_H_UP`／`_LI_EXP`／`_FI_BUY`）。
_GOLDEN_NEW = [
    ('markdown',
     '<div style="margin:34px 0 10px;padding:12px 18px;background:linear-gradient(90deg,#ff7b722b,#ff7b720a,#0d1117);border-left:6px solid #ff7b72;border-radius:0 10px 10px 0;"><span style="font-size:12px;color:#ff7b72;font-weight:700;opacity:0.85;">拐點</span><div style="font-size:18px;font-weight:900;color:#ff7b72;margin-top:2px;">🔮 拐點</div><div style="font-size:12px;color:#8b949e;margin-top:2px;">六大面向 × CPI×Fed 雙頂回落（景氣反轉偵測）</div></div>'),
    ('markdown',
     '<div style="background:#161b22;border-left:4px solid #ef4444;border-radius:0 8px 8px 0;padding:8px 12px;margin:6px 0;font-size:13px;font-weight:600;color:#ef4444;">🔴 綜合拐點：6 群中 2 群偏空（可評估 2/6 群）→ 偏向頂部起跌</div>'),
    ('caption',
     '趨勢（均線結構）：未評估\u3000位階（乖離率）：未評估\u3000資金（M1B-M2 / 台幣）：未評估\u3000籌碼（外資期貨 / 韭菜 / 外資連續）：偏空\u3000景氣（NDC 對策 / 領先指標）：偏空\u3000通膨利率（CPI × Fed）：未評估'),
    ('caption',
     '💡 同一群內的訊號（例：外資期貨大空單＋散戶極度看多）源自同一個潛在因子，**群內取最壞、不累加** —— 避免把同一件事數成多份獨立證據而誇大確信度。'),
    ('caption',
     '⚠️ 未評估：趨勢（均線結構）、位階（乖離率）、資金（M1B-M2 / 台幣）、通膨利率（CPI × Fed）（資料未取得 → 已排除於分母外，既不計入偏多也不計入偏空）'),
    ('markdown',
     '##### 📊 拐點詳細分析 — 六大面向 + CPI×Fed 雙頂回落'),
    ('markdown',
     "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #ef4444;border-radius:8px;padding:8px 10px;margin:3px 0;min-height:54px;display:flex;align-items:center;'><span style='color:#ef4444;font-weight:700;font-size:13px;'>⚠️ 景氣對策連2月翻空</span></div>"),
    ('markdown',
     "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #ef4444;border-radius:8px;padding:8px 10px;margin:3px 0;min-height:54px;display:flex;align-items:center;'><span style='color:#ef4444;font-weight:700;font-size:13px;'>❌ 領先指標持續收縮</span></div>"),
    ('markdown',
     "<div style='background:#0d1117;border:1px solid #21262d;border-top:3px solid #ef4444;border-radius:8px;padding:8px 10px;margin:3px 0;min-height:54px;display:flex;align-items:center;'><span style='color:#ef4444;font-weight:700;font-size:13px;'>❌ 外資連續賣超</span></div>"),
    ('expander',
     '🔍 拐點六大面向 — 完整訊號明細 + 判斷參考'),
    ('markdown',
     '<div style="background:#0d1117;border-left:3px solid #ef4444;border-radius:0 6px 6px 0;padding:6px 10px;margin:4px 0;"><span style="color:#ef4444;font-weight:600;">⚠️ 景氣對策連2月翻空</span><br><span style="color:#8b949e;font-size:12px;">分數 26→24 由升轉跌 → 景氣動能衰退拐點</span></div>'),
    ('markdown',
     '<div style="background:#0d1117;border-left:3px solid #ef4444;border-radius:0 6px 6px 0;padding:6px 10px;margin:4px 0;"><span style="color:#ef4444;font-weight:600;">❌ 領先指標持續收縮</span><br><span style="color:#8b949e;font-size:12px;">6M smoothed change -0.35% 維持負值 → 景氣收縮</span></div>'),
    ('markdown',
     '<div style="background:#0d1117;border-left:3px solid #ef4444;border-radius:0 6px 6px 0;padding:6px 10px;margin:4px 0;"><span style="color:#ef4444;font-weight:600;">❌ 外資連續賣超</span><br><span style="color:#8b949e;font-size:12px;">外資已連 6 日賣超 → 籌碼流出警示</span></div>'),
    ('caption',
     '📖 拐點判斷參考表 → 詳見「策略手冊」Tab'),
]
#: 84c1ca4 實跑：舊快取那一組（`_H_UP`／`_LI_EXP`／`_FI_BUY`）的頭句與 `_pivot_signals`。
_HEAD_OLD = '🟢 綜合拐點：6 群中 2 群偏多（可評估 2/6 群）→ 偏向底部起漲'
_PIVOTS_OLD = [
    ('景氣對策連2月翻多', '🚀', '#22c55e', '分數 24→26 由跌轉升 → 景氣領先翻揚拐點'),
    ('領先指標持續擴張', '✅', '#22c55e', '6M smoothed change +0.42% 維持正值 → 景氣擴張'),
    ('外資連續買超', '✅', '#22c55e', '外資已連 6 日買超 → 籌碼穩健'),
]
#: 84c1ca4 實跑：只有一支換成新值（其餘兩支沿用舊值）時的頭句與 `_pivot_signals`。
_ONE_NEW = {
    '_ndc_hist_cache': (
        '⚪ 訊號分歧：偏多 1 群 vs 偏空 1 群（可評估 2/6 群），方向待確認',
        [
            ('景氣對策連2月翻空', '⚠️', '#ef4444', '分數 26→24 由升轉跌 → 景氣動能衰退拐點'),
            ('領先指標持續擴張', '✅', '#22c55e', '6M smoothed change +0.42% 維持正值 → 景氣擴張'),
            ('外資連續買超', '✅', '#22c55e', '外資已連 6 日買超 → 籌碼穩健'),
        ]),
    '_ndc_li_cache': (
        '⚪ 訊號分歧：偏多 1 群 vs 偏空 1 群（可評估 2/6 群），方向待確認',
        [
            ('景氣對策連2月翻多', '🚀', '#22c55e', '分數 24→26 由跌轉升 → 景氣領先翻揚拐點'),
            ('領先指標持續收縮', '❌', '#ef4444', '6M smoothed change -0.35% 維持負值 → 景氣收縮'),
            ('外資連續買超', '✅', '#22c55e', '外資已連 6 日買超 → 籌碼穩健'),
        ]),
    '_fi_streak_cache': (
        '⚪ 訊號分歧：偏多 1 群 vs 偏空 1 群（可評估 2/6 群），方向待確認',
        [
            ('景氣對策連2月翻多', '🚀', '#22c55e', '分數 24→26 由跌轉升 → 景氣領先翻揚拐點'),
            ('領先指標持續擴張', '✅', '#22c55e', '6M smoothed change +0.42% 維持正值 → 景氣擴張'),
            ('外資連續賣超', '❌', '#ef4444', '外資已連 6 日賣超 → 籌碼流出警示'),
        ]),
}
#: 驗收補測（B 組 S9）—— 84c1ca4 實跑：真 L1（領先指標 `[100]*11+[99.99]`）產生 `smooth6m=-0.0`、
#: 景氣對策失敗、外資震盪時的頭句與 `_pivot_signals`。📌 批 Z11（Z5-n3）起改判持平，兩常數僅留作修前紀錄。
_HEAD_REAL_NEGZERO = '⚪ 訊號分歧：偏多 0 群 vs 偏空 1 群（可評估 2/6 群），方向待確認'
_PIVOTS_REAL_NEGZERO = [
    ('領先指標 6M 由正轉負', '⚠️', '#ef4444', '6M smoothed change：+0.00%→-0.00% → 景氣轉折下行'),
]

#: 84c1ca4 實跑：`_macro_session_reset` 修前的清除名單（本批只**加**三個 key，這 11 個一個都不能少）。
_RESET_KEYS_84C1CA4 = ("cl_data", "cl_ts", "mkt_info", "jingqi_info", "li_latest",
                       "warroom_summary", "_last_inst", "_last_inst_date",
                       "_last_margin", "futures_net", "adl_debug_msg")

#: 修後畫面字 —— 全部是 L2 `aggregate_pivot_families` 既有字樣（頭句三種分母、群名、說明尾句）。
_HEAD_2 = "⚪ 訊號分歧：偏多 0 群 vs 偏空 0 群（可評估 2/6 群），方向待確認"   # 修前失敗時也印這句
_HEAD_1 = "⚪ 拐點資料不足：6 群僅 1 群可評估 → 不宣稱方向"
_HEAD_0 = "⚪ 拐點資料不足：6 群僅 0 群可評估 → 不宣稱方向"
_CHIPS = "籌碼（外資期貨 / 韭菜 / 外資連續）"
_CYCLE = "景氣（NDC 對策 / 領先指標）"
_NOTE_TAIL = "（資料未取得 → 已排除於分母外，既不計入偏多也不計入偏空）"


def _families(chips: str, cycle: str) -> str:
    return "　".join([
        "趨勢（均線結構）：未評估", "位階（乖離率）：未評估", "資金（M1B-M2 / 台幣）：未評估",
        f"{_CHIPS}：{chips}", f"{_CYCLE}：{cycle}", "通膨利率（CPI × Fed）：未評估"])


def _note(chips_unevaluated: bool, cycle_unevaluated: bool) -> str:
    names = ["趨勢（均線結構）", "位階（乖離率）", "資金（M1B-M2 / 台幣）"]
    if chips_unevaluated:
        names.append(_CHIPS)
    if cycle_unevaluated:
        names.append(_CYCLE)
    names.append("通膨利率（CPI × Fed）")
    return "⚠️ 未評估：" + "、".join(names) + _NOTE_TAIL


def _expected_flat(chips_ok: bool, cycle_ok: bool) -> list:
    """無訊號情境的完整輸出：`_GOLDEN_FLAT` 只換頭句、分群明細、未評估說明三格（其餘逐字不動）。"""
    n = int(chips_ok) + int(cycle_ok)
    head = {2: _HEAD_2, 1: _HEAD_1, 0: _HEAD_0}[n]
    out = list(_GOLDEN_FLAT)
    assert _HEAD_2 in out[1][1]
    out[1] = ("markdown", out[1][1].replace(_HEAD_2, head))
    out[2] = ("caption", _families("中性" if chips_ok else "未評估",
                                   "中性" if cycle_ok else "未評估"))
    out[4] = ("caption", _note(not chips_ok, not cycle_ok))
    return out


def test_expected_flat_is_golden_when_all_usable():
    """自我檢查：兩群都可評估時 `_expected_flat` 就是 84c1ca4 的 golden（建構式沒有偷改別格）。"""
    assert _expected_flat(True, True) == _GOLDEN_FLAT


# ══════════════════════════════════════════════════════════════════════════
# C7-n1 —— runner
# ══════════════════════════════════════════════════════════════════════════
class _StateRun:
    def __init__(self, out, calls, fake):
        self.out = out
        self.calls = dict(calls)
        self.fake = fake

    @property
    def text(self) -> str:
        return "\n".join(t for _k, t in self.out)

    @property
    def cached(self) -> dict:
        return {k: self.fake.session_state[k] for k in _KEYS if k in self.fake.session_state}

    @property
    def pivots(self) -> list:
        return [tuple(p) for p in self.fake.session_state.get("_pivot_signals") or []]


def _render_state(mp, h, li, fi, *, fake=None, ss=None) -> _StateRun:
    """§二 拐點面板：面板 1~5／7 全空（`_mkt_info` 只有空訊號），只看面板 6 的三支。"""
    calls = {"h": 0, "li": 0, "fi": 0}

    def _mk(tag, val):
        def _fetch(**_kw):
            calls[tag] += 1
            return copy.deepcopy(val)
        return _fetch

    mp.setattr(TW, "fetch_ndc_signal_history", _mk("h", h))
    mp.setattr(TW, "fetch_ndc_leading_index", _mk("li", li))
    mp.setattr(TW, "fetch_foreign_consecutive_days", _mk("fi", fi))
    fake = fake if fake is not None else _FakeST(ss)
    mp.setattr(STATE, "st", fake)
    n0 = len(fake.out)
    STATE.render_section_state({"signals": []}, None, None, {},
                               show_market_data=False, requested=True)
    return _StateRun(fake.out[n0:], calls, fake)


# ══════════════════════════════════════════════════════════════════════════
# C7-n1 ① ② —— 失敗／無值不再被說成「中性」，也不算進「可評估 N/6 群」
# ══════════════════════════════════════════════════════════════════════════
class TestC7n1FailureIsUnevaluated:

    def test_all_three_fail(self, monkeypatch):
        """修前：頭句「可評估 2/6 群」＋「籌碼…：中性　景氣…：中性」（＝`_GOLDEN_FLAT`）。"""
        r = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL)
        assert r.out == _expected_flat(chips_ok=False, cycle_ok=False)
        assert _HEAD_0 in r.text and "可評估 2/6 群" not in r.text
        assert f"{_CHIPS}：中性" not in r.text and f"{_CYCLE}：中性" not in r.text
        assert r.out != _GOLDEN_FLAT                      # 84c1ca4 在這個情境印的就是它
        assert r.pivots == []

    def test_fi_latest_day_missing(self, monkeypatch):
        """外資「最新一日缺」（error=None、consec_days=None）：修前登記籌碼群、印「中性」。"""
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_LATEST_MISSING)
        assert r.out == _expected_flat(chips_ok=False, cycle_ok=True)
        assert _HEAD_1 in r.text and f"{_CHIPS}：未評估" in r.text

    #: 外資那一支的各種「沒有可用值」形狀（L1 原形 ＋ 代表值缺／非有限）
    _FI_SHAPES = {
        "l1_fetch_failed": _FI_FAIL,
        "l1_json_failed": dict(_FI_FAIL, error="FinMind JSON 解析失敗: Expecting value"),
        "l1_no_foreign_rows": dict(_FI_FAIL, error="FinMind 無 Foreign_Investor 資料"),
        "l1_too_few_rows": dict(_FI_FAIL, error="外資資料筆數不足"),
        "latest_day_missing": _FI_LATEST_MISSING,
        "consec_nan": dict(_FI_FLAT, consec_days=float("nan")),
        "consec_pos_inf": dict(_FI_FLAT, consec_days=float("inf")),
        "consec_neg_inf": dict(_FI_FLAT, consec_days=float("-inf")),
        "consec_np_nan": dict(_FI_FLAT, consec_days=np.float64("nan")),
        "consec_none": dict(_FI_FLAT, consec_days=None),
        "consec_key_absent": {k: v for k, v in _FI_FLAT.items() if k != "consec_days"},
        "error_with_value": dict(_FI_FLAT, error="FinMind 抓取失敗"),
        "result_none": None,
        "result_empty_dict": {},
        # 驗收補測（A 組 B2／B 組 S5）：`error=''` 也是失敗（與 L1 `_no_error` 的 `is None` 一致）
        "error_empty_string": dict(_FI_FLAT, error=""),
        # 驗收補測（B 組 S10／S12）：bool 與數字字串不是可用值（沿用 `_finite_yoy` 的判準）
        "consec_bool_true": dict(_FI_FLAT, consec_days=True),
        "consec_bool_false": dict(_FI_FLAT, consec_days=False),
        "consec_numeric_string": dict(_FI_FLAT, consec_days="5"),
        # 驗收補測（B 組重驗 S5b）：`error=False`／`error=0` 也是「有 error」（L1 `_no_error` 只認 `is None`）
        "error_false": dict(_FI_FLAT, error=False),
        "error_zero": dict(_FI_FLAT, error=0),
    }

    @pytest.mark.parametrize("shape", sorted(_FI_SHAPES))
    def test_fi_unusable_shapes(self, shape, monkeypatch):
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, self._FI_SHAPES[shape])
        assert r.out == _expected_flat(chips_ok=False, cycle_ok=True), shape
        assert "_fi_streak_cache" not in r.cached, "沒有可用值的結果不得寫進 session 快取"
        assert set(r.cached) == {"_ndc_hist_cache", "_ndc_li_cache"}

    #: 景氣群要「兩支都沒有可用值」才是未評估（同一份國發會資料集，任一支可用即可評估）
    _CYCLE_SHAPES = {
        "l1_both_failed": (_H_FAIL, _LI_FAIL),
        "l1_other_errors": (_H_FAIL_SANITY, _LI_FAIL_MA),
        "values_nan": (dict(_H_FLAT, score_latest=float("nan")),
                       dict(_LI_FLAT, smooth6m=float("nan"))),
        "values_pos_inf": (dict(_H_FLAT, score_latest=float("inf")),
                           dict(_LI_FLAT, smooth6m=float("inf"))),
        "values_neg_inf": (dict(_H_FLAT, score_latest=float("-inf")),
                           dict(_LI_FLAT, smooth6m=float("-inf"))),
        "values_none": (dict(_H_FLAT, score_latest=None), dict(_LI_FLAT, smooth6m=None)),
        "keys_absent": ({k: v for k, v in _H_FLAT.items() if k != "score_latest"},
                        {k: v for k, v in _LI_FLAT.items() if k != "smooth6m"}),
        "error_with_value": (dict(_H_FLAT, error="x"), dict(_LI_FLAT, error="y")),
        "results_none": (None, None),
        "mixed_fail_and_nan": (_H_FAIL, dict(_LI_FLAT, smooth6m=float("nan"))),
        # 驗收補測（A 組 B2／B 組 S5、S10、S12）
        "error_empty_string": (dict(_H_FLAT, error=""), dict(_LI_FLAT, error="")),
        "values_bool": (dict(_H_FLAT, score_latest=True), dict(_LI_FLAT, smooth6m=False)),
        "values_numeric_string": (dict(_H_FLAT, score_latest="25"),
                                  dict(_LI_FLAT, smooth6m="0.0")),
        # 驗收補測（B 組重驗 S5b、S10F_h、S10T_li）：error=False／0；bool 兩支對調（h=False、li=True）
        "error_false": (dict(_H_FLAT, error=False), dict(_LI_FLAT, error=False)),
        "error_zero": (dict(_H_FLAT, error=0), dict(_LI_FLAT, error=0)),
        "values_bool_swapped": (dict(_H_FLAT, score_latest=False), dict(_LI_FLAT, smooth6m=True)),
    }

    @pytest.mark.parametrize("shape", sorted(_CYCLE_SHAPES))
    def test_cycle_unusable_shapes(self, shape, monkeypatch):
        h, li = self._CYCLE_SHAPES[shape]
        r = _render_state(monkeypatch, h, li, _FI_FLAT)
        assert r.out == _expected_flat(chips_ok=True, cycle_ok=False), shape
        assert set(r.cached) == {"_fi_streak_cache"}

    @pytest.mark.parametrize("h,li,cached", [
        pytest.param(_H_FAIL, _LI_FLAT, {"_ndc_li_cache", "_fi_streak_cache"},
                     id="hist-failed-leading-ok"),
        pytest.param(_H_FLAT, _LI_FAIL, {"_ndc_hist_cache", "_fi_streak_cache"},
                     id="hist-ok-leading-failed"),
    ])
    def test_one_of_two_ndc_usable_keeps_cycle(self, h, li, cached, monkeypatch):
        """景氣群只要其中一支可用就可評估 —— 畫面與 84c1ca4 逐字相同；只有失敗那支不進快取
        （驗收補測：逐 key 釘住哪兩支入快取，⛔ 只數個數）。"""
        r = _render_state(monkeypatch, h, li, _FI_FLAT)
        assert r.out == _GOLDEN_FLAT
        assert set(r.cached) == cached

    def test_hist_failed_signals_from_others_unchanged(self, monkeypatch):
        """景氣對策失敗、領先指標與外資都有訊號：頭句與訊號與 84c1ca4 相同（實跑同值）。"""
        r = _render_state(monkeypatch, _H_FAIL, _LI_EXP, _FI_SELL)
        assert r.pivots == _GOLDEN_SIGNALS_PIVOTS[1:]
        assert "⚪ 訊號分歧：偏多 1 群 vs 偏空 1 群（可評估 2/6 群），方向待確認" in r.text
        assert "_ndc_hist_cache" not in r.cached

    def test_chips_still_evaluable_from_leading_indicators(self, monkeypatch):
        """籌碼群另有先行指標（`li_latest` 的外資期貨／韭菜）時，外資連續失敗不影響籌碼群 ——
        只擋「面板 6 自己沒資料」，⛔ 把整群打成未評估（實跑：fi 失敗那格與 84c1ca4 逐字相同）。"""
        li = pd.DataFrame({"外資大小": [-1000.0, 5000.0], "韭菜指數": [1.0, 0.0]})   # 不觸發訊號
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FAIL, ss={"li_latest": li})
        assert r.out == _GOLDEN_FLAT
        r = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL, ss={"li_latest": li})
        assert r.out == _expected_flat(chips_ok=True, cycle_ok=False)


class TestC7n1RealL1FailureShape:
    """不替換 fetcher，只把 L1 的 `fetch_url` 換成「無回應」—— 三支真的 L1 函式自己產生失敗 dict。"""

    def test_real_l1_failures_are_unevaluated_and_not_cached(self, monkeypatch):
        monkeypatch.setattr(TW, "fetch_url", lambda *a, **k: None)
        # 先確認 L1 這三支在「無回應」時回的確實是帶 error 的 dict（本批要擋的正是這個形狀）
        assert TW.fetch_ndc_signal_history(months_back=12, token="")["error"]
        assert TW.fetch_ndc_leading_index(months_back=18, token="")["error"]
        assert TW.fetch_foreign_consecutive_days(days_back=30, token="")["error"] == "FinMind 抓取失敗"
        fake = _FakeST()
        monkeypatch.setattr(STATE, "st", fake)
        STATE.render_section_state({"signals": []}, None, None, {},
                                   show_market_data=False, requested=True)
        assert fake.out == _expected_flat(chips_ok=False, cycle_ok=False)
        assert not any(k in fake.session_state for k in _KEYS)


# ══════════════════════════════════════════════════════════════════════════
# C7-n1 —— 正常值：完整輸出與 84c1ca4 逐字相同
# ══════════════════════════════════════════════════════════════════════════
class TestC7n1NormalUnchanged:

    def test_flat_matches_golden(self, monkeypatch):
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FLAT)
        assert r.out == _GOLDEN_FLAT
        assert r.pivots == []

    def test_signals_match_golden(self, monkeypatch):
        r = _render_state(monkeypatch, _H_UP, _LI_EXP, _FI_SELL)
        assert r.out == _GOLDEN_SIGNALS
        assert r.pivots == _GOLDEN_SIGNALS_PIVOTS

    def test_zero_values_are_values(self, monkeypatch):
        """`smooth6m=0.0`、`consec_days=0` 是真的值（不是缺）—— 84c1ca4 照樣登記，修後不得改判未評估。"""
        li0 = dict(_LI_FLAT, smooth6m=0.0, prev_s6m=0.0)
        fi0 = dict(_FI_FLAT, consec_days=0, prev_streak=0, today_net=0)
        h_li_only = dict(_H_FAIL)                      # 景氣群只靠領先指標的 0.0 撐住
        r = _render_state(monkeypatch, h_li_only, li0, fi0)
        assert r.out == _GOLDEN_FLAT
        assert set(r.cached) == {"_ndc_li_cache", "_fi_streak_cache"}

    def test_usable_results_are_cached(self, monkeypatch):
        r = _render_state(monkeypatch, _H_UP, _LI_EXP, _FI_SELL)
        assert r.cached == {"_ndc_hist_cache": _H_UP, "_ndc_li_cache": _LI_EXP,
                            "_fi_streak_cache": _FI_SELL}

    def test_cached_values_are_reused_without_refetch(self, monkeypatch):
        """session 已有可用結果 → 不重抓、直接用（84c1ca4 的既有行為不變）。"""
        ss = {"_ndc_hist_cache": copy.deepcopy(_H_UP), "_ndc_li_cache": copy.deepcopy(_LI_EXP),
              "_fi_streak_cache": copy.deepcopy(_FI_SELL)}
        r = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL, ss=ss)
        assert r.calls == {"h": 0, "li": 0, "fi": 0}
        assert r.out == _GOLDEN_SIGNALS


class TestC7n1UsableValueShapes:
    """驗收補測（B 組 S9／S11）：「可用值」的判準逐型別釘住 —— 這裡是**算可用**的那一側
    （bool、數字字串、`error=''` 算不可用，見 `TestC7n1FailureIsUnevaluated` 的兩張形狀表）。
    每一支都同時驗畫面（群算不算可評估）與快取（入不入、下一輪重不重抓）。"""

    @pytest.mark.parametrize("h_val,li_val,fi_val", [
        pytest.param(np.int64(25), np.float64(0.0), np.int64(2), id="numpy-int64"),
        pytest.param(np.float64(25.0), np.float32(0.0), np.float64(5.0), id="numpy-float"),
    ])
    def test_numpy_scalars_are_usable(self, h_val, li_val, fi_val, monkeypatch):
        """numpy 純量是真的數值：與 84c1ca4 一樣兩群可評估（明細「中性」）、入快取、下一輪不重抓。"""
        fake = _FakeST()
        r1 = _render_state(monkeypatch, dict(_H_FLAT, score_latest=h_val),
                           dict(_LI_FLAT, smooth6m=li_val), dict(_FI_FLAT, consec_days=fi_val),
                           fake=fake)
        assert r1.out == _GOLDEN_FLAT
        assert set(r1.cached) == set(_KEYS)
        r2 = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL, fake=fake)
        assert r2.calls == {"h": 0, "li": 0, "fi": 0}
        assert r2.out == _GOLDEN_FLAT

    @pytest.mark.parametrize("val", [pytest.param(np.True_, id="np-True"),
                                     pytest.param(np.False_, id="np-False")])
    def test_numpy_bool_currently_usable(self, val, monkeypatch):
        """只鎖現行輸出，⛔ 不代表語意背書；與共用 `_finite_yoy` 一致，語意待 Z3-n3 裁定，屆時可有意識地改這支測試。

        現行：numpy bool（`np.True_`／`np.False_`）判「可用」—— 共用 `_finite_yoy` 只排除 Python bool
        （總管 2026-10-05 裁定本批不改正式碼、不另立規則）。L1 這三支不會產出 numpy bool；
        Python bool 判不可用見 `_FI_SHAPES`／`_CYCLE_SHAPES`。釘住的行為：兩群可評估（明細「中性」，
        完整輸出＝84c1ca4 的 `_GOLDEN_FLAT`）、三支入快取、下一輪不重抓。"""
        fake = _FakeST()
        r1 = _render_state(monkeypatch, dict(_H_FLAT, score_latest=val),
                           dict(_LI_FLAT, smooth6m=val), dict(_FI_FLAT, consec_days=val), fake=fake)
        assert r1.out == _GOLDEN_FLAT
        assert set(r1.cached) == set(_KEYS)
        r2 = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL, fake=fake)
        assert r2.calls == {"h": 0, "li": 0, "fi": 0}
        assert r2.out == _GOLDEN_FLAT

    @pytest.mark.parametrize("h,li,side", [
        pytest.param(dict(_H_FLAT, score_latest=np.int64(25)), _LI_FAIL, "h", id="h-np-int64"),
        pytest.param(dict(_H_FLAT, score_latest=np.True_), _LI_FAIL, "h", id="h-np-True"),
        pytest.param(dict(_H_FLAT, score_latest=np.False_), _LI_FAIL, "h", id="h-np-False"),
        pytest.param(dict(_H_FLAT, score_latest=0), _LI_FAIL, "h", id="h-zero"),
        pytest.param(_H_FAIL, dict(_LI_FLAT, smooth6m=np.float64(0.42)), "li", id="li-np-float64"),
        pytest.param(_H_FAIL, dict(_LI_FLAT, smooth6m=np.True_), "li", id="li-np-True"),
        pytest.param(_H_FAIL, dict(_LI_FLAT, smooth6m=np.False_), "li", id="li-np-False"),
    ])
    def test_cycle_single_side_usable(self, h, li, side, monkeypatch):
        """驗收補測（B 組逐 key 掃描）：景氣群只有**一支**可用（另一支失敗）時，由那一支單獨撐起「可評估」——
        畫面＝`_GOLDEN_FLAT`（景氣「中性」）、那一支入快取、下一輪不重抓（失敗那支照常重抓）。
        上面幾支把兩支設成同型別，「任一支可用即可評估」的 OR 會蓋掉單邊的錯；這裡逐支拆開。
        畫面與 84c1ca4 逐字相同（實跑）。np.True_／np.False_ 兩格同屬：只鎖現行輸出，⛔ 不代表語意背書；
        與共用 `_finite_yoy` 一致，語意待 Z3-n3 裁定，屆時可有意識地改這兩格。"""
        key = {"h": "_ndc_hist_cache", "li": "_ndc_li_cache"}[side]
        fake = _FakeST()
        r1 = _render_state(monkeypatch, h, li, _FI_FLAT, fake=fake)
        assert r1.out == _GOLDEN_FLAT
        assert set(r1.cached) == {key, "_fi_streak_cache"}
        r2 = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL, fake=fake)
        assert r2.calls == {"h": int(side != "h"), "li": int(side != "li"), "fi": 0}
        assert r2.out == _GOLDEN_FLAT

    @pytest.mark.parametrize("h,li,fi,cached,calls2", [
        # 景氣群只靠景氣對策那支（領先指標失敗）→ 兩個呼叫點（寫快取／登記）都只看 score_latest
        pytest.param(dict(_H_FLAT, score_latest=-0.0), _LI_FAIL, _FI_FLAT,
                     {"_ndc_hist_cache", "_fi_streak_cache"}, {"h": 0, "li": 1, "fi": 0},
                     id="score_latest"),
        # 籌碼群只靠外資連續那支（沒有先行指標）
        pytest.param(_H_FLAT, _LI_FLAT, dict(_FI_FLAT, consec_days=-0.0),
                     set(_KEYS), {"h": 0, "li": 0, "fi": 0}, id="consec_days"),
    ])
    def test_negative_zero_representative_is_a_value(self, h, li, fi, cached, calls2, monkeypatch):
        """驗收補測（B 組重驗 S9c／CZ，h 與 fi 兩支）：代表值 -0.0 是真的 0（⛔ 缺）—— 該群照舊可評估
        （完整輸出＝`_GOLDEN_FLAT`，明細「中性」）、入快取、下一輪不重抓（以本 head 實跑釘住）。"""
        fake = _FakeST()
        r1 = _render_state(monkeypatch, h, li, fi, fake=fake)
        assert r1.out == _GOLDEN_FLAT
        assert set(r1.cached) == cached
        r2 = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL, fake=fake)
        assert r2.calls == calls2
        assert r2.out == _GOLDEN_FLAT

    def test_negative_zero_smooth6m_is_a_value(self, monkeypatch):
        """`smooth6m=-0.0` 是真的 0（⛔ 缺）：景氣群照舊可評估、入快取、下一輪不重抓（84c1ca4 同值）。"""
        fake = _FakeST()
        li0 = dict(_LI_FLAT, smooth6m=-0.0, prev_s6m=-0.0)
        r1 = _render_state(monkeypatch, _H_FAIL, li0, _FI_FLAT, fake=fake)
        assert r1.out == _GOLDEN_FLAT
        assert set(r1.cached) == {"_ndc_li_cache", "_fi_streak_cache"}
        r2 = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL, fake=fake)
        assert r2.calls == {"h": 1, "li": 0, "fi": 0}
        assert r2.out == _GOLDEN_FLAT

    def test_real_l1_negative_zero_is_cached(self, monkeypatch):
        """真 L1 產得出 -0.0：領先指標 `[100]*11+[99.99]` → `smooth6m=-0.0`。
        入快取、下一輪不重抓。
        📌 批 Z11（Z5-n3，客戶 Q-r9b ②）：L1 改以兩位小數判轉折 ⇒ 此例由「⚠️ 由正轉負」（84c1ca4 印
        `_PIVOTS_REAL_NEGZERO` 的「+0.00%→-0.00%」＋`_HEAD_REAL_NEGZERO`）改判「📊 持平」、不亮燈 ⇒
        畫面＝`_GOLDEN_FLAT`。本測的主旨（-0.0 是真的值、入快取、不重抓）不變。"""
        tbi = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=12, freq="MS").strftime("%Y-%m-%d"),
            "monitoring": [25] * 12, "leading": [100.0] * 11 + [99.99]})
        monkeypatch.setattr(TW, "fetch_business_indicator_series", lambda *a, **k: tbi)
        li_real = TW.fetch_ndc_leading_index(months_back=18, token="")
        assert li_real["error"] is None and li_real["inflection"] == "📊 持平"
        assert li_real["smooth6m"] == 0.0 and math.copysign(1.0, li_real["smooth6m"]) == -1.0
        fake = _FakeST()
        r1 = _render_state(monkeypatch, _H_FAIL, li_real, _FI_FLAT, fake=fake)
        assert r1.pivots == [] and r1.out == _GOLDEN_FLAT
        assert set(r1.cached) == {"_ndc_li_cache", "_fi_streak_cache"}
        r2 = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL, fake=fake)
        assert r2.calls == {"h": 1, "li": 0, "fi": 0}
        assert r2.pivots == [] and r2.out == _GOLDEN_FLAT


# ══════════════════════════════════════════════════════════════════════════
# C7-n1 ② —— 一次失敗不再凍住整個 session
# ══════════════════════════════════════════════════════════════════════════
class TestC7n1NoFreezeAcrossReruns:

    def test_failed_round_then_recovered_upstream(self, monkeypatch):
        fake = _FakeST()
        r1 = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL, fake=fake)
        assert r1.out == _expected_flat(chips_ok=False, cycle_ok=False)
        assert r1.cached == {}
        # 下一次 rerun：上游已恢復 —— 必須重抓並看得到（84c1ca4：0 次重抓、照印失敗那一輪）
        r2 = _render_state(monkeypatch, _H_UP, _LI_EXP, _FI_SELL, fake=fake)
        assert r2.calls == {"h": 1, "li": 1, "fi": 1}
        assert r2.out == _GOLDEN_SIGNALS
        # 再下一次：可用結果已進快取 → 不再重抓
        r3 = _render_state(monkeypatch, _H_FAIL, _LI_FAIL, _FI_FAIL, fake=fake)
        assert r3.calls == {"h": 0, "li": 0, "fi": 0}
        assert r3.out == _GOLDEN_SIGNALS

    def test_latest_day_missing_then_recovered(self, monkeypatch):
        fake = _FakeST()
        r1 = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_LATEST_MISSING, fake=fake)
        assert f"{_CHIPS}：未評估" in r1.text
        r2 = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FLAT, fake=fake)
        assert r2.calls == {"h": 0, "li": 0, "fi": 1}
        assert r2.out == _GOLDEN_FLAT

    def test_preloaded_failure_dict_is_not_counted(self, monkeypatch):
        """session 裡已躺著失敗 dict（例：修前那一版寫進去的）→ 不重抓也不得算可評估。"""
        ss = {"_ndc_hist_cache": copy.deepcopy(_H_FAIL), "_ndc_li_cache": copy.deepcopy(_LI_FAIL),
              "_fi_streak_cache": copy.deepcopy(_FI_FAIL)}
        r = _render_state(monkeypatch, _H_FLAT, _LI_FLAT, _FI_FLAT, ss=ss)
        assert r.calls == {"h": 0, "li": 0, "fi": 0}
        assert r.out == _expected_flat(chips_ok=False, cycle_ok=False)


# ══════════════════════════════════════════════════════════════════════════
# C7-n1 ③ —— 一鍵更新／強制重抓清得掉這三個快取
# ══════════════════════════════════════════════════════════════════════════
def _seeded_session() -> dict:
    ss = {k: f"old-{k}" for k in _RESET_KEYS_84C1CA4}
    ss.update({"_ndc_hist_cache": copy.deepcopy(_H_FAIL), "_ndc_li_cache": copy.deepcopy(_LI_FAIL),
               "_fi_streak_cache": copy.deepcopy(_FI_FAIL),
               "chips_loaded": True, "macro_info": {"x": 1}, "_macro_ai_report": "keep"})
    return ss


class TestC7n1SessionReset:

    def _after(self, monkeypatch, handler) -> dict:
        fake = _FakeST(_seeded_session())
        monkeypatch.setattr(H, "st", fake)
        handler()
        return fake.session_state

    @staticmethod
    def _quiet_force_clear(monkeypatch):
        """強制重抓的另外三層（pkl／st.cache_data／proxy）換成離線替身，只驗 session 那一層。"""
        import src.services as SV
        from src.data.proxy import proxy_helper as PH
        monkeypatch.setattr(SV, "_pkl_clear_all", lambda: None, raising=False)
        monkeypatch.setattr(PH, "_URL_CACHE", {})
        monkeypatch.setattr(PH, "reset_proxy_cache", lambda: None)

    def test_reset_pops_the_three_caches_and_keeps_the_rest(self, monkeypatch):
        ss = self._after(monkeypatch, H._macro_session_reset)
        assert not any(k in ss for k in _KEYS)
        assert not any(k in ss for k in _RESET_KEYS_84C1CA4)     # 修前名單一個都沒少
        assert ss == {"chips_loaded": True, "macro_info": {"x": 1}, "_macro_ai_report": "keep",
                      "_is_refreshing": True}

    def test_refresh_button_handler(self, monkeypatch):
        ss = self._after(monkeypatch, H._on_refresh_click)
        assert not any(k in ss for k in _KEYS)

    def test_force_refresh_button_handler(self, monkeypatch):
        self._quiet_force_clear(monkeypatch)
        ss = self._after(monkeypatch, H._on_force_clear_click)
        assert not any(k in ss for k in _KEYS)
        assert ss["_is_refreshing"] is True

    def test_after_reset_section_refetches_and_shows_new_values(self, monkeypatch):
        """按更新後的那一輪：面板 6 重新向 L1 要，畫面換成新結果（修前：沿用舊快取、0 次重抓）。"""
        fake = _FakeST(_seeded_session())
        monkeypatch.setattr(H, "st", fake)
        H._macro_session_reset()
        r = _render_state(monkeypatch, _H_UP, _LI_EXP, _FI_SELL, fake=fake)
        assert r.calls == {"h": 1, "li": 1, "fi": 1}
        assert r.out == _GOLDEN_SIGNALS

    # ── 驗收補測（A 組 B1）：舊快取是**可用**值時，重設也要清掉並重抓 ───────────────────
    #   上面幾支的種子是失敗 dict；「重設只清不可用快取」的突變在那幾支會存活。下面兩支改用
    #   可用的舊值（`_H_UP`／`_LI_EXP`／`_FI_BUY`，84c1ca4 實跑頭句「🟢 綜合拐點：6 群中 2 群偏多…」）。
    @staticmethod
    def _usable_old_session() -> dict:
        # 只放三個可用的舊快取（＋按過更新的旗標）：按更新**前**也要能正常 render 一輪，
        # 故不放 `_seeded_session()` 那些字串佔位值（`cl_data` 等是字串時 §二 會拋）。
        return {"_ndc_hist_cache": copy.deepcopy(_H_UP), "_ndc_li_cache": copy.deepcopy(_LI_EXP),
                "_fi_streak_cache": copy.deepcopy(_FI_BUY), "chips_loaded": True}

    def test_reset_drops_usable_caches_too(self, monkeypatch):
        """按更新前：沿用可用的舊快取、不重抓（頭句「🟢 …2 群偏多」）；按更新後：三支都重抓、
        畫面＝新值的完整輸出（頭句「🔴 綜合拐點：6 群中 2 群偏空…」），⛔ 沿用舊值。"""
        fake = _FakeST(self._usable_old_session())
        r0 = _render_state(monkeypatch, _H_DOWN, _LI_CON, _FI_SELL, fake=fake)
        assert r0.calls == {"h": 0, "li": 0, "fi": 0}
        assert r0.pivots == _PIVOTS_OLD and _HEAD_OLD in r0.text
        monkeypatch.setattr(H, "st", fake)
        H._macro_session_reset()
        r1 = _render_state(monkeypatch, _H_DOWN, _LI_CON, _FI_SELL, fake=fake)
        assert r1.calls == {"h": 1, "li": 1, "fi": 1}
        assert r1.out == _GOLDEN_NEW
        assert _HEAD_OLD not in r1.text

    @pytest.mark.parametrize("key", _KEYS)
    def test_reset_drops_each_usable_cache(self, key, monkeypatch):
        """逐一釘住：只有 `key` 那支上游換了新值 —— 按更新後那一支必須換成新值
        （任何一個 key 被重設漏掉都會單獨轉紅；頭句與訊號以 84c1ca4 全新 session 實跑寫死）。"""
        new = {"_ndc_hist_cache": _H_DOWN, "_ndc_li_cache": _LI_CON, "_fi_streak_cache": _FI_SELL}
        old = {"_ndc_hist_cache": _H_UP, "_ndc_li_cache": _LI_EXP, "_fi_streak_cache": _FI_BUY}
        src = {k: (new[k] if k == key else old[k]) for k in _KEYS}
        fake = _FakeST(self._usable_old_session())
        monkeypatch.setattr(H, "st", fake)
        H._macro_session_reset()
        r = _render_state(monkeypatch, src["_ndc_hist_cache"], src["_ndc_li_cache"],
                          src["_fi_streak_cache"], fake=fake)
        head, pivots = _ONE_NEW[key]
        assert r.pivots == pivots and head in r.text
        assert r.calls == {"h": 1, "li": 1, "fi": 1}


# ══════════════════════════════════════════════════════════════════════════
# C7-n8 —— §十一 AI 裁決 prompt
# ══════════════════════════════════════════════════════════════════════════
_FUT_LINE = "• 外資期貨淨口數："
_LEEK_LINE = "• 韭菜指數（小台法人空多比）："
_ADL_LINE = "• ADL 漲跌家數比（上漲家數佔全市場 %）："
_FUT_TAIL = ("（單位為 TX 當量口＝大台淨口＋0.25×小台淨口，非原始口數加總；負=淨空單；"
             "畫面燈號同一套門檻：≤-10000口 🟡 警戒、≤-20000口 🔴 危險；另有系統硬否決線："
             "淨口 <-35000 口「且」指數同時跌破 MA5 → 強制曝險上限 30%，此線比燈號嚴屬設計）")
_LEEK_TAIL = ("（值域 ±100%、中性 0%；>+20% 散戶偏熱、>+30% 極端過熱（頂部訊號）；"
              "<-30% 極端悲觀（軋空動能）)")
_ADL_TAIL = "（畫面燈號同一套門檻：≤50.0% 🟡 警戒、≤35.0% 🔴 危險）"

#: 84c1ca4 實跑：三欄末列皆為 NaN 時 prompt 的三行（本批要擋掉的東西；±inf 同型，印「+inf 口」等）。
_PRE_FIX_NAN_LINES = (
    _LEEK_LINE + "+nan%" + _LEEK_TAIL,
    _ADL_LINE + "nan%" + _ADL_TAIL,
    _FUT_LINE + "+nan 口" + _FUT_TAIL,
)

#: 驗收補測（B 組 N13）：有限但極大的值照送（只有 NaN／±inf／溢位才不送）。
#: 本 head 實跑：prompt 裡 1e18 的整數位（同上去掉正負號與小數部分），19 位。
_DIGITS_1E18 = "1000000000000000000"
#: 84c1ca4 實跑：prompt 裡 1e301 的整數位（`:+.0f`／`:+.1f`／`:.0f` 去掉正負號與小數部分），302 位。
_DIGITS_1E301 = (
    "100000000000000005250476025520442024870446858110815915491585"
    "411551180245798890819578637137508044786404370444383288387817"
    "694252323536043057564479218478670698284838720092657580373783"
    "023379478809005936895323497079994508111903896764088007465274"
    "278014249457925878882005684283811566947219638686545940054016"
    "00"
)
#: 84c1ca4 實跑：同上，1.7976931348623157e308（float 最大有限值），309 位。
_DIGITS_FLOAT_MAX = (
    "179769313486231570814527423731704356798070567525844996598917"
    "476803157260780028538760589558632766878171540458953514382464"
    "234321326889464182768467546703537516986049910576551282076245"
    "490090389328944075868508455133942304583236903222948165808559"
    "332123348274797826204144723168738177180919299881250404026184"
    "124858368"
)

#: 84c1ca4 實跑：完整 prompt（外資大小 −23456.0／韭菜指數 12.34／ad_ratio 61.7）。逐行寫死。
_GOLDEN_PROMPT_FINITE = '\n'.join([
    '你是一個很會「把複雜的投資資訊翻成人話」的朋友，正在幫一個完全不懂股票的人看懂下面這份「台股大盤現在的狀況」的資料。',
    '',
    '【講話規則 — 一定要遵守】',
    '1. 用「跟完全不懂股票的長輩或朋友聊天解釋」的白話口吻，能講人話就不要拽詞。',
    '2. 嚴禁專業術語裸用。若非用不可（如 殖利率、乖離、KD、折溢價、Sharpe），',
    '   務必馬上用括號附超白話解釋，例：「殖利率（你買進後一年大概能領回幾 % 現金）」。',
    '3. 重點不是堆數字，而是「這代表好還是壞、該開心還是擔心、要注意什麼」。',
    '4. 不要喊「一定要買 / 保證賺 / 必漲 / 快進場」這種話。',
    '5. 全程繁體中文，語氣親切、簡短，不要落落長。',
    '6. 只能根據上方各節「已提供的數字」說明；**嚴禁自行虛構任何價格、代號、比率、日期或結論**。',
    '   某項資料沒有就直說「這項沒有資料」，絕不腦補一個數字、也不編一檔沒被列出的股票（§1 反捏造）。',
    '',
    '下面是各章節的原始數據（都幫你算好了），請逐節用白話解讀：',
    '',
    '【第1節：現在市場是偏多還偏空（系統幫你下的判斷）】',
    '{',
    '  "market_regime": "震盪",',
    '  "systemic_risk_level": "警告",',
    '  "exposure_limit_pct": 60,',
    '  "Macro_Phase": "7 項未評估（缺資料不計分）",',  # 批 Z9 X2-n1：缺 7 項 → 改字（客戶 2026-10-06 裁）
    '  "missing_inputs": [',
    '    "VIX_Index",',
    '    "ISM_PMI_or_OECD_CLI",',
    '    "PMI_Prev_Month",',
    '    "M1B_YoY_pct",',
    '    "M2_YoY_pct",',
    '    "BIAS240_pct",',
    '    "PCR"',
    '  ]',
    '}',
    '',
    '【第2節：景氣、資金、利率這些關鍵數字現在長怎樣】',
    '• 韭菜指數（小台法人空多比）：+12.3%（值域 ±100%、中性 0%；>+20% 散戶偏熱、>+30% 極端過熱（頂部訊號）；<-30% 極端悲觀（軋空動能）)',
    '• ADL 漲跌家數比（上漲家數佔全市場 %）：62%（畫面燈號同一套門檻：≤50.0% 🟡 警戒、≤35.0% 🔴 危險）',
    '• 外資期貨淨口數：-23456 口（單位為 TX 當量口＝大台淨口＋0.25×小台淨口，非原始口數加總；負=淨空單；畫面燈號同一套門檻：≤-10000口 🟡 警戒、≤-20000口 🔴 危險；另有系統硬否決線：淨口 <-35000 口「且」指數同時跌破 MA5 → 強制曝險上限 30%，此線比燈號嚴屬設計）',
    '',
    '【第3節：熱錢動向（三角交叉：外資 × 台幣匯率 × 背離）】',
    '（無熱錢資料）',
    '',
    '【第4節：拐點訊號（六大面向綜合判斷，偵測景氣反轉）】',
    '（拐點訊號尚未計算，請先載入總經拼圖）',
    '',
    '【最近相關新聞 / 時事】',
    '（無法取得新聞）',
    '',
    '【輸出格式 — 用 Markdown，務必逐節對應】',
    '## 🧾 台股大盤現在的狀況｜白話總整理',
    '',
    '⚠️ **硬規定（缺一不可）**：以下 4 個章節**全部都要輸出**，順序與名稱完全照下方清單，',
    '缺資料的章節也必須保留標題，並用一句話說明「為什麼缺資料 / 看不出來」，不准跳過、不准合併：',
    '',
    '  1. 第1節：現在市場是偏多還偏空（系統幫你下的判斷）',
    '  2. 第2節：景氣、資金、利率這些關鍵數字現在長怎樣',
    '  3. 第3節：熱錢動向（三角交叉：外資 × 台幣匯率 × 背離）',
    '  4. 第4節：拐點訊號（六大面向綜合判斷，偵測景氣反轉）',
    '',
    '每節都用這個格式輸出（節名沿用上面的章節名稱）：',
    '### 第N節：<章節名稱>',
    '- 用 2~3 句白話講：這節在看什麼、現在狀況是好是壞、要開心還是擔心、要注意什麼。',
    '',
    '全部 4 節講完後，再加兩段：',
    '### 📰 最近發生了什麼事（時事）',
    '- 從上面新聞挑「跟這個標的真的有關」的 1~3 件，白話講「發生什麼、對它是好消息還壞消息」。',
    '  若沒抓到新聞，就老實說「最近沒抓到相關新聞」，不要硬掰。',
    '### ✅ 一句話總結',
    '- 用一句最白話的話總結：現在大盤整體偏多還偏空、適不適合進場、最該留意什麼。',
    '- 最後另起一行附小字：「以上只是把資料翻成白話幫你理解，不是投資建議，買賣請自己決定。」',
])


def _frames(fut=-23456.0, leek=12.34, adl=61.7, *, drop=(), dtype=None):
    """`li_latest`（外資大小／韭菜指數）＋ `cl_data['adl']`（ad_ratio）；`drop` 拿掉指定欄（＝缺欄）。"""
    li = {"外資大小": [-1000.0, fut], "韭菜指數": [5.0, leek]}
    ad = {"ad_ratio": [50.0, adl]}
    for _c in drop:
        li.pop(_c, None)
        ad.pop(_c, None)
    li_df = pd.DataFrame(li if li else {"x": [1, 2]}, dtype=dtype)
    ad_df = pd.DataFrame(ad if ad else {"y": [1, 2]}, dtype=dtype)
    return li_df, ad_df


def _run_news(mp, li_df, adl_df) -> dict:
    """§十一：按下「🔒 執行 AI 裁決」→ 攔下送 Gemini 的 prompt、規則引擎的輸入與輸出、鎖定的狀態。"""
    import src.data.news as N
    import src.services.app_ai_service as A
    from src.services.macro_state_locker import calculate_system_state as _real_calc
    ss = {"li_latest": li_df, "cl_data": ({"adl": adl_df} if adl_df is not None else {})}
    fake = _FakeST(ss, clicked={"btn_run_verdict"})
    seen: dict = {"prompts": [], "numbers": [], "states": [], "locked": []}

    class _Locker:                       # 不寫 macro_state.json
        def lock_system_state_only(self, state):
            seen["locked"].append(state)

    def _spy_calc(nums):                 # 只記錄、原樣交給 L3 本尊
        seen["numbers"].append(dict(nums))
        out = _real_calc(nums)
        seen["states"].append(out)
        return out

    mp.setattr(NEWS, "st", fake)
    mp.setattr(NEWS, "render_macro_bucket_summary_bar", lambda *a, **k: None)
    mp.setattr(NEWS, "MacroStateLocker", _Locker)
    mp.setattr(NEWS, "calculate_system_state", _spy_calc)
    mp.setattr(A, "gemini_call",
               lambda p, max_tokens=2048: seen["prompts"].append(p) or "（測試替身報告）")
    mp.setattr(N, "fetch_macro_news", lambda *a, **k: [])
    with pytest.raises(_Rerun):
        NEWS.render_section_news_ai({}, "unknown")
    assert len(seen["prompts"]) == 1, "沒有走到 Gemini 替身"
    seen["prompt"] = seen["prompts"][0]
    seen["lines"] = [ln for ln in seen["prompt"].splitlines()
                     if ln.startswith((_FUT_LINE, _LEEK_LINE, _ADL_LINE))]
    return seen


#: 欄位 → (被拿掉的欄名, 那一行的開頭)
_FIELDS = {"fut": ("外資大小", _FUT_LINE), "leek": ("韭菜指數", _LEEK_LINE),
           "adl": ("ad_ratio", _ADL_LINE)}

#: 非有限（或轉不成有限 float）的值 —— 修後一律當缺
_BAD = {
    "nan": float("nan"),
    "pos_inf": float("inf"),
    "neg_inf": float("-inf"),
    "np_float64_nan": np.float64("nan"),
    "np_float32_nan": np.float32("nan"),
    "np_float64_inf": np.float64("inf"),
    "str_nan": "nan",
    "str_inf": "inf",
    "str_neg_infinity": "-Infinity",
    "str_overflow": "1e400",
    "huge_int": 10 ** 400,               # 84c1ca4：float() 拋 OverflowError，整個裁決流程崩潰
}


class TestC7n8NonFiniteDropsTheLine:

    def test_all_three_nan(self, monkeypatch):
        """修前：三行各印「+nan%」「nan%」「+nan 口」（`_PRE_FIX_NAN_LINES`）。"""
        nan = float("nan")
        seen = _run_news(monkeypatch, *_frames(nan, nan, nan))
        assert seen["lines"] == []
        assert not any(ln in seen["prompt"] for ln in _PRE_FIX_NAN_LINES)
        assert seen["numbers"][0]["Futures_Net_Short"] is None
        absent = _run_news(monkeypatch, *_frames(drop=("外資大小", "韭菜指數", "ad_ratio")))
        assert seen["prompt"] == absent["prompt"]       # ＝三欄都缺的既有輸出（整行不送）
        assert seen["states"] == absent["states"] and seen["locked"] == absent["locked"]

    @pytest.mark.parametrize("bad", sorted(_BAD))
    @pytest.mark.parametrize("field", sorted(_FIELDS))
    def test_one_field_non_finite(self, field, bad, monkeypatch):
        vals = {"fut": -23456.0, "leek": 12.34, "adl": 61.7}
        vals[field] = _BAD[bad]
        seen = _run_news(monkeypatch, *_frames(**vals, dtype=object))
        col, head = _FIELDS[field]
        assert not any(ln.startswith(head) for ln in seen["lines"]), seen["lines"]
        for ln in seen["lines"]:
            assert "nan" not in ln and "inf" not in ln, ln
        # 其餘兩行與 84c1ca4 逐字相同；整份 prompt ＝ 該欄不存在時的 prompt（既有缺值路徑）
        golden = [ln for ln in _GOLDEN_PROMPT_FINITE.splitlines()
                  if ln.startswith((_FUT_LINE, _LEEK_LINE, _ADL_LINE)) and not ln.startswith(head)]
        assert seen["lines"] == golden
        absent = _run_news(monkeypatch, *_frames(drop=(col,)))
        assert seen["prompt"] == absent["prompt"]
        assert seen["states"] == absent["states"] and seen["locked"] == absent["locked"]
        if field == "fut":
            assert seen["numbers"][0]["Futures_Net_Short"] is None

    def test_engine_output_same_as_missing(self, monkeypatch):
        """規則引擎本來就把 NaN 當缺：送 None 與修前送 NaN 的引擎輸出相同（含 missing_inputs）。"""
        from src.services.macro_state_locker import calculate_system_state as calc
        seen = _run_news(monkeypatch, *_frames(fut=float("nan")))
        as_nan = dict(seen["numbers"][0], Futures_Net_Short=float("nan"))
        assert calc(as_nan) == seen["states"][0]
        assert "Futures_Net_Short" in seen["states"][0]["missing_inputs"]


class TestC7n8FiniteUnchanged:

    def test_full_prompt_matches_golden(self, monkeypatch):
        seen = _run_news(monkeypatch, *_frames())
        assert seen["prompt"] == _GOLDEN_PROMPT_FINITE
        assert seen["numbers"][0]["Futures_Net_Short"] == -23456.0

    #: 84c1ca4 實跑：(外資大小, 韭菜指數, ad_ratio) → 三行的數字部分（各行尾句同 `_*_TAIL`）
    _FINITE = {
        "floats": ((-23456.0, 12.34, 61.7), ("+12.3%", "62%", "-23456 口"), -23456.0),
        "object_ints": ((-15000, -7, 44), ("-7.0%", "44%", "-15000 口"), -15000.0),
        "numeric_strings": (("-12000", "8.5", "47.2"), ("+8.5%", "47%", "-12000 口"), -12000.0),
        "numpy_scalars": ((np.float64(-31234.5), np.int64(-4), np.float32(38.5)),
                          ("-4.0%", "38%", "-31234 口"), -31234.5),
        "negative_zero": ((-0.0, -0.0, -0.0), ("-0.0%", "-0%", "-0 口"), -0.0),
        # 驗收補測（B 組逐 key 掃描）：+0.0（正式路徑走得到：淨口數、空多比剛好為 0）三行照送，84c1ca4 實跑
        "positive_zero": ((0.0, 0.0, 0.0), ("+0.0%", "0%", "+0 口"), 0.0),
    }

    @pytest.mark.parametrize("name", sorted(_FINITE))
    def test_finite_lines_match_golden(self, name, monkeypatch):
        (fut, leek, adl), (leek_s, adl_s, fut_s), fut_in = self._FINITE[name]
        seen = _run_news(monkeypatch, *_frames(fut, leek, adl, dtype=object))
        assert seen["lines"] == [_LEEK_LINE + leek_s + _LEEK_TAIL,
                                 _ADL_LINE + adl_s + _ADL_TAIL,
                                 _FUT_LINE + fut_s + _FUT_TAIL]
        assert seen["numbers"][0]["Futures_Net_Short"] == fut_in

    @pytest.mark.parametrize("fut,leek,adl,dtype,signs,digits", [
        pytest.param(1e301, 1e301, 1e301, None, ("+", "+", ""), _DIGITS_1E301, id="pos-1e301"),
        pytest.param(-1e301, -1e301, -1e301, None, ("-", "-", "-"), _DIGITS_1E301, id="neg-1e301"),
        pytest.param(1e301, -1e301, 1e301, object, ("+", "-", ""), _DIGITS_1E301,
                     id="mixed-1e301-object"),
        pytest.param(1.7976931348623157e308, -1.7976931348623157e308, 1.7976931348623157e308, None,
                     ("+", "-", ""), _DIGITS_FLOAT_MAX, id="float-max"),
        # 驗收補測（B 組重驗 N13band）：中段大值（1e18）三欄各一、正負各一 —— 殺「只丟某一段大值」一類突變
        pytest.param(1e18, 1e18, 1e18, None, ("+", "+", ""), _DIGITS_1E18, id="pos-1e18"),
        pytest.param(-1e18, -1e18, -1e18, None, ("-", "-", "-"), _DIGITS_1E18, id="neg-1e18"),
    ])
    def test_large_finite_values_still_sent(self, fut, leek, adl, dtype, signs, digits, monkeypatch):
        """驗收補測（B 組 N13／重驗 N13band）：有限但很大（1e18、1e301、float 最大值）不是缺值 ——
        三行照送、逐字＝實跑（1e301／最大值＝84c1ca4；1e18＝本 head），規則引擎照收原值；
        ⛔ 拿「很大」當不送的理由（只有 NaN／±inf／溢位才不送）。"""
        seen = _run_news(monkeypatch, *_frames(fut, leek, adl, dtype=dtype))
        fut_s, leek_s, adl_s = signs
        assert seen["lines"] == [_LEEK_LINE + leek_s + digits + ".0%" + _LEEK_TAIL,
                                 _ADL_LINE + adl_s + digits + "%" + _ADL_TAIL,
                                 _FUT_LINE + fut_s + digits + " 口" + _FUT_TAIL]
        assert seen["numbers"][0]["Futures_Net_Short"] == fut

    @pytest.mark.parametrize("li_df,adl_df", [
        pytest.param(None, None, id="no-li-latest-no-adl"),
        pytest.param(pd.DataFrame({"x": [1, 2]}), pd.DataFrame({"y": [1, 2]}), id="columns-absent"),
        pytest.param(pd.DataFrame({"外資大小": [1.0, None], "韭菜指數": [1.0, None]}, dtype=object),
                     pd.DataFrame({"ad_ratio": [1.0, None]}, dtype=object), id="none-values"),
        pytest.param(*_frames("-", "-", "-", dtype=object), id="dash-strings"),
        pytest.param(pd.DataFrame({"外資大小": [], "韭菜指數": []}),
                     pd.DataFrame({"ad_ratio": []}), id="empty-frames"),
    ])
    def test_missing_stays_missing(self, li_df, adl_df, monkeypatch):
        """84c1ca4 在這幾種缺值本來就整行不送（實跑三行皆無）—— 修後不變。"""
        seen = _run_news(monkeypatch, li_df, adl_df)
        assert seen["lines"] == []
        assert seen["numbers"][0]["Futures_Net_Short"] is None


# ══════════════════════════════════════════════════════════════════════════
# slow lane —— 真 Streamlit（AppTest）
# ══════════════════════════════════════════════════════════════════════════
def _app(body: str):
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest
    import pathlib
    repo = str(pathlib.Path(__file__).resolve().parents[1])
    at = AppTest.from_string(
        "import sys\n"
        f"sys.path.insert(0, {repo!r})\n"
        "import streamlit as st\n" + body, default_timeout=90)
    # 面板 6 讀 `st.secrets.get('FINMIND_TOKEN')`；沒有 secrets 檔時真 Streamlit 會拋
    # StreamlitSecretNotFoundError、整個面板 6 被 except 吞掉 —— 那就驗不到抓取路徑。
    at.secrets["FINMIND_TOKEN"] = ""
    return at


def _app_ok(at) -> None:
    if at.exception:
        pytest.fail("render 有 uncaught exception:\n" + "\n".join(
            f"{e.type}: {str(e.value)[:300]}" for e in at.exception))


_APP_STATE = ("from src.ui.tabs.macro.section_state import render_section_state\n"
              "render_section_state({'signals': []}, st.empty(), st.empty(), {}, "
              "show_market_data=False, requested=True)\n")


@pytest.mark.slow
class TestRealStreamlitZ5:

    def test_state_failure_not_frozen_across_reruns(self, monkeypatch):
        box = {"h": _H_FAIL, "li": _LI_FAIL, "fi": _FI_FAIL}
        calls = {"h": 0, "li": 0, "fi": 0}

        def _mk(tag):
            def _fetch(**_kw):
                calls[tag] += 1
                return copy.deepcopy(box[tag])
            return _fetch
        monkeypatch.setattr(TW, "fetch_ndc_signal_history", _mk("h"))
        monkeypatch.setattr(TW, "fetch_ndc_leading_index", _mk("li"))
        monkeypatch.setattr(TW, "fetch_foreign_consecutive_days", _mk("fi"))
        at = _app(_APP_STATE)
        at.run()
        _app_ok(at)
        caps = [c.value for c in at.caption]
        assert _families("未評估", "未評估") in caps
        assert any(_HEAD_0 in m.value for m in at.markdown)
        assert not any(k in at.session_state for k in _KEYS)
        assert calls == {"h": 1, "li": 1, "fi": 1}
        # 上游恢復 → 下一次 rerun 重抓、畫面換成真結果
        box.update(h=_H_FLAT, li=_LI_FLAT, fi=_FI_FLAT)
        at.run()
        _app_ok(at)
        assert calls == {"h": 2, "li": 2, "fi": 2}
        assert _families("中性", "中性") in [c.value for c in at.caption]
        assert all(k in at.session_state for k in _KEYS)
        # 可用結果已進快取 → 再 rerun 不重抓
        at.run()
        _app_ok(at)
        assert calls == {"h": 2, "li": 2, "fi": 2}

    def test_news_nan_real_click(self, monkeypatch):
        import src.data.news as N
        import src.services.app_ai_service as A
        prompts: list = []

        class _Locker:
            def lock_system_state_only(self, state):
                pass
        monkeypatch.setattr(A, "gemini_call",
                            lambda p, max_tokens=2048: prompts.append(p) or "（替身）")
        monkeypatch.setattr(N, "fetch_macro_news", lambda *a, **k: [])
        monkeypatch.setattr(NEWS, "MacroStateLocker", _Locker)
        at = _app(
            "import pandas as pd\n"
            "st.session_state['li_latest'] = pd.DataFrame("
            "{'外資大小': [-1000.0, float('nan')], '韭菜指數': [5.0, float('inf')]})\n"
            "st.session_state['cl_data'] = {'adl': pd.DataFrame({'ad_ratio': [50.0, float('-inf')]})}\n"
            "from src.ui.tabs.macro.section_news_ai import render_section_news_ai\n"
            "render_section_news_ai({}, 'unknown')\n")
        at.run()
        _app_ok(at)
        at.button(key="btn_run_verdict").click().run()
        _app_ok(at)
        assert len(prompts) == 1, "真按鈕沒有走到 Gemini 替身"
        assert not any(ln.startswith((_FUT_LINE, _LEEK_LINE, _ADL_LINE))
                       for ln in prompts[0].splitlines())
        assert "+nan" not in prompts[0] and "inf%" not in prompts[0] and "inf 口" not in prompts[0]
