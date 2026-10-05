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

golden：以 origin/main `84c1ca4`（修前）在本檔同一個 harness 實跑後**寫死** —— ⛔ 在測試裡讀 git、
⛔ 由程式反推。正常值的完整輸出與修前逐字相同（`_GOLDEN_*`）。
harness：`_FakeST` 以 monkeypatch 換掉被測模組的 module-level `st`；L1 fetcher、Gemini、新聞 RSS、
狀態鎖一律換成離線替身。本檔不觸網、不寫檔。slow lane 另以真 Streamlit（AppTest）驗 rerun 行為。
"""
from __future__ import annotations

import copy

import numpy as np
import pytest

import src.data.macro.tw_macro as TW
import src.ui.tabs.macro.handlers as H
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
    }

    @pytest.mark.parametrize("shape", sorted(_CYCLE_SHAPES))
    def test_cycle_unusable_shapes(self, shape, monkeypatch):
        h, li = self._CYCLE_SHAPES[shape]
        r = _render_state(monkeypatch, h, li, _FI_FLAT)
        assert r.out == _expected_flat(chips_ok=True, cycle_ok=False), shape
        assert set(r.cached) == {"_fi_streak_cache"}

    @pytest.mark.parametrize("h,li", [
        pytest.param(_H_FAIL, _LI_FLAT, id="hist-failed-leading-ok"),
        pytest.param(_H_FLAT, _LI_FAIL, id="hist-ok-leading-failed"),
    ])
    def test_one_of_two_ndc_usable_keeps_cycle(self, h, li, monkeypatch):
        """景氣群只要其中一支可用就可評估 —— 畫面與 84c1ca4 逐字相同；只有失敗那支不進快取。"""
        r = _render_state(monkeypatch, h, li, _FI_FLAT)
        assert r.out == _GOLDEN_FLAT
        assert len(r.cached) == 2 and "_fi_streak_cache" in r.cached

    def test_hist_failed_signals_from_others_unchanged(self, monkeypatch):
        """景氣對策失敗、領先指標與外資都有訊號：頭句與訊號與 84c1ca4 相同（實跑同值）。"""
        r = _render_state(monkeypatch, _H_FAIL, _LI_EXP, _FI_SELL)
        assert r.pivots == _GOLDEN_SIGNALS_PIVOTS[1:]
        assert "⚪ 訊號分歧：偏多 1 群 vs 偏空 1 群（可評估 2/6 群），方向待確認" in r.text
        assert "_ndc_hist_cache" not in r.cached


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

    def test_usable_results_cached_as_same_object(self, monkeypatch):
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
