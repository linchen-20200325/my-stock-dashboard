"""批 Z8（2026-10-06）—— Z5-n1 釘子（L5 only：`section_traffic_light`／`macro_classroom`；基底 origin/main `24bf2af`）。

Z5-n1（第九輪分類 A、B 兩組皆實跑重現；總管轉述）
────────────────────────────────────────────────────────────────
全部來源失敗後按「🚀 一鍵更新全部數據」：同一輪 ^TWII（市場評估）與旌旗（ADL＋^TWII）兩條腿都缺 ⇒
L2 `calc_traffic_light` 回 `health=None`（設計如此：arbiter 回 UNLOADED_VERDICT）⇒
`render_traffic_light_top` 寫 `warroom_summary['throttle']` 時無條件 `float(None)` 拋 TypeError ⇒
`tab_macro` 的 `st.rerun` 之後整個「總經」分頁被 app.py `_render_tab_isolated` 換成紅框
「⚠️ 「總經」分頁渲染異常,已隔離(其他分頁不受影響):TypeError: float() argument must be a string or a real
number, not 'NoneType'」；快取新鮮的 30 分鐘內每次 rerun 都再炸一次。
修法：
① `section_traffic_light`：health 為 None 時不呼叫 `compute_position_throttle`，throttle 寫 None
   （與 L3 `allocation_service.get_allocation` 同一寫法；該 key 已無程式讀者）。health 有值時呼叫與引數逐字不變。
   `tests/test_position_throttle_ssot.py` 的原始碼字串掃描照樣過 —— `compute_position_throttle(` 仍是一行真的
   程式碼（在 health 有值時執行，見 `TestTopWithValuesUnchanged` 的 throttle 斷言），不是只剩註解。
② `macro_classroom`（📖 為何紅綠燈是現在這個顏色）：健康評分／市場分數為 None 時改印同檔既有的「— 未取得」，
   ⛔ 不印「None」；判 `is not None`（0 是合法值，不可當成未取得）；有值時逐字不變。
畫面只用既有字樣（`24bf2af` 逐字可找到）；⛔ 新增字句、⛔ 填 0。

harness（fast lane）
────────────────────────────────────────────────────────────────
`_FakeST`（沿用 `tests/test_m2n2_no_zero_fill.py`，批 Z6 先例）以 monkeypatch 換掉被測模組的 module-level
`st`；L2 `calc_traffic_light`、L3 `load_section_inputs`／`get_macro_state`／`get_allocation` 全是真的
（讀同一個假 session）。時鐘固定（快取 09:00、現在 09:05 ＝ 新鮮）；決策門檻釘在 35／4（＝基底
`macro_thresholds.json` 的值；季度校準 workflow 改門檻時本檔的 golden 不跟著漂）；cwd 換到 tmp（`get_macro_state`
讀相對路徑 `macro_state.json`，工作目錄有沒有那個檔不得影響結果）。本檔不觸網、不寫 repo 內任何檔。

golden：於基底 `24bf2af`（修前）以本檔同一支 harness 實跑後**寫死**（⛔ 在測試裡讀 git、⛔ 由程式反推）。
- 有值（N1～N5、explainer 四個舊 fixture 形狀）：`render_traffic_light_top` 的整份輸出＋`warroom_summary`
  ＋`macro_state`＋回傳值、explainer 整份輸出、§二 尾端（燈號卡→油門→explainer）整份輸出 —— 修後 sha256
  與修前逐位相同（`_BASE_*`）。
- 缺值：修後輸出以「還原替換」（把唯一預期改變的那幾行換回修前寫法）後 sha256 必須等於修前 golden ——
  等於斷言「除了這幾行，整份輸出逐字與基底相同」（`_undo`）。修前 `render_traffic_light_top` 在 F1～F4
  是拋例外（沒有輸出可比），改以修後實跑寫死的 sha（`_FIXED_TOP_SHA`，實作組於修後碼實跑）＋逐項行為斷言。
- 「修前拋例外」另以還原體（`TestRevertedIsTheBug`，原始碼字面替換）重現 —— 那一類是字面錨點，⛔ 不算殺突變。

slow lane（真 Streamlit AppTest）
────────────────────────────────────────────────────────────────
① 最小重現：預置「全敗後」session → `render_traffic_light_top()`（連跑兩輪 ＝ rerun）。
② 整個總經分頁（app.py `_render_tab_isolated` 以 AST 抽出原文包住）＋預置 session。
③ mock 全部來源失敗：網路在 HTTP 層一律拒絕（requests／curl_cffi／urllib／socket），pickle 快取目錄、
   `st.cache_data`、proxy URL 快取都換成空的；冷啟動連按兩次「🚀 一鍵更新全部數據」（第一下只設旗標，
   C9-n3，範圍外），走真的抓取段 → `st.rerun` → 最終畫面。先行指標那支 job 以「逾時 → None」處理
   （批 Z5-n1 A 組真網路實跑的形狀：`li_latest` 不存在）—— 理由見下方「範圍外」第 1 點。

範圍外（實作組實跑發現，⚠️ 單組；本檔 ⛔ 釘住、⛔ 修）
────────────────────────────────────────────────────────────────
1. C8-n1 (a)：先行指標回「14 列、數值全 None」時（本沙箱斷網實跑 `build_leading_fast` 即此形狀），修後頁面
   往下跑到 `section_chips.py` 約 L266 `float(_li4.iloc[-1].get('外資大小', 0))` 拋**同一句** TypeError，
   紅框原字不變（批 Z7 的檔）。故 ③ 把那支 job 設成 None，只驗本批這一個拋出點。
2. explainer（本批②改的同一個函式）在 health=None 時：
   (a) 規則表第 2 條的 `_health < HEALTH_DEFENSE_THRESHOLD`（修前約 L157）對 None 拋 TypeError，被
       `section_state.py` 的 try/except 吞掉 ⇒ 展開後「🎯 判讀規則」標題下方整段（五條規則、背後原理、
       校準說明）不見，只寫 stdout；
   (b) 「⚖️ 這兩個值不一樣是正常的：…第 1/2 條(總經惡化)優先命中並覆蓋了它 → 最終「unknown」」—— 實際是
       沒有資料、沒有任何一條命中，屬錯結論；同區「趨勢面 regime：neutral」來自 L2 `mkt_info` 缺時的預設值。
   修前這兩件在全敗時看不到（整頁紅框）；修後才露出。修法要決定「未評估時規則表怎麼標」，屬規格未定，停手回報。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import importlib.util
import json
import pathlib
import re
import types

import pandas as pd
import pytest

import src.compute.macro.macro_helpers as MH
import src.services.allocation_service as AS
import src.ui.tabs.macro.handlers as H
import src.ui.tabs.macro.section_state as SS
import src.ui.tabs.macro.section_traffic_light as STL
import src.ui.tabs.macro_classroom as MC
from src.compute.macro import calc_traffic_light
from tests.test_m2n2_no_zero_fill import _FakeST

_REPO = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════════════
# harness
# ══════════════════════════════════════════════════════════════════════════
#: 固定時鐘：快取時戳 09:00、現在 09:05 ⇒ 快取新鮮（< 30 分）、非刷新中。
_CL_TS = "2026-10-06 09:00"


class _FixedDT(_dt.datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: D401 — 測試替身
        return cls(2026, 10, 6, 9, 5)


_FIXED_DT_MOD = types.SimpleNamespace(datetime=_FixedDT)

#: 基底 `macro_thresholds.json` 的值（golden 擷取時用的就是這兩個）。
_PIN_HEALTH_DEFENSE, _PIN_BULL_MIN = 35, 4


def _deny_network(monkeypatch, tmp_path) -> list:
    """全部來源失敗：網路在 HTTP 層一律拒絕；本地快取全部從空的開始；cwd 換到空目錄。

    ⚠️ 只擋連線、不改任何 fetcher：各 L1 照自己的失敗路徑走（重試、降級、回 None／空表）。
    同一個 pytest process 裡別的測試寫過的 pickle／`st.cache_data`／proxy URL 快取一律不算數。
    回傳被拒絕的請求清單（斷言「真的有去抓、真的失敗」，不是剛好沒呼叫）。
    """
    import socket
    import urllib.request

    import requests
    import requests.adapters

    denied: list = []

    def _deny_requests(self, request, *a, **k):
        denied.append(getattr(request, "url", "?"))
        raise requests.exceptions.ConnectionError("批 Z8 測試：連線一律拒絕（全部來源失敗）")

    def _deny(*a, **k):
        denied.append("socket/urllib")
        raise ConnectionError("批 Z8 測試：連線一律拒絕（全部來源失敗）")

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", _deny_requests)
    monkeypatch.setattr(urllib.request, "urlopen", _deny)
    monkeypatch.setattr(socket.socket, "connect", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)
    try:
        import curl_cffi.requests as _cr
    except ImportError:  # pragma: no cover — 沒裝就沒有這條路
        _cr = None
    if _cr is not None:
        def _deny_curl(self, method, url, *a, **k):
            denied.append(url)
            raise ConnectionError("批 Z8 測試：連線一律拒絕（curl_cffi）")

        async def _deny_curl_async(self, method, url, *a, **k):
            denied.append(url)
            raise ConnectionError("批 Z8 測試：連線一律拒絕（curl_cffi async）")
        monkeypatch.setattr(_cr.Session, "request", _deny_curl)
        monkeypatch.setattr(_cr.AsyncSession, "request", _deny_curl_async)

    import shared.app_cache as _ac
    import shared.cache_layer as _cl
    from src.data.proxy import proxy_helper as _ph
    monkeypatch.setattr(_cl, "_PKL_DIR", str(tmp_path / "pkl"))
    monkeypatch.setattr(_ac, "_CACHE_DIR", str(tmp_path / "pkl"))
    monkeypatch.setattr(_ph, "_URL_CACHE", {})
    for _k in ("FRED_API_KEY", "FINMIND_TOKEN", "GEMINI_API_KEY", "NAS_BASE_URL"):
        monkeypatch.delenv(_k, raising=False)
    monkeypatch.chdir(tmp_path)
    return denied


@pytest.fixture
def _pinned(monkeypatch, tmp_path):
    """fast lane 每一支都要：門檻釘死、不觸網、cwd 換到空目錄。"""
    monkeypatch.setattr(MH, "HEALTH_DEFENSE_THRESHOLD", _PIN_HEALTH_DEFENSE)
    monkeypatch.setattr(MH, "BULL_MIN_SCORE", _PIN_BULL_MIN)
    monkeypatch.setattr(MC, "HEALTH_DEFENSE_THRESHOLD", _PIN_HEALTH_DEFENSE)
    monkeypatch.setattr(MC, "BULL_MIN_SCORE", _PIN_BULL_MIN)
    _deny_network(monkeypatch, tmp_path)
    return monkeypatch


def _base_state() -> dict:
    """「按過一鍵更新、資料剛寫回」的 session 共同部分（快取新鮮、非刷新中、已請求）。"""
    return {"cl_ts": _CL_TS, "_is_refreshing": False, "chips_loaded": True}


def _cl_data(*, inst=None, adl=None) -> dict:
    """tab_macro 抓取段寫回的 `cl_data` 形狀（`st.session_state['cl_data'] = dict(intl=…, adl=…)`）。"""
    return dict(intl={}, tw={}, tech={}, inst=({} if inst is None else inst),
                inst_date=None, margin=None, adl=adl)


def _li(fut, leek=(-12.0, -8.0, -5.0, -3.0)) -> pd.DataFrame:
    return pd.DataFrame({"_date": ["20261001", "20261002", "20261005", "20261006"],
                         "外資大小": list(fut), "韭菜指數": list(leek)})


_INST = {"外資": {"net": 15.2}, "投信": {"net": 3.1}, "自營商": {"net": -1.0}}
_ADL = pd.DataFrame({"ad_ratio": [55.0, 58.0, 60.0]})


def _scenario(name: str) -> dict:
    s = _base_state()
    if name == "F1_all_failed":          # Z5-n1 原型（A 組實跑後的 session 形狀）
        s["cl_data"] = _cl_data()
    elif name == "F2_inst_none_legacy":  # 舊版 session：inst=None（coerce_inst_dict 收斂成 {}）
        s["cl_data"] = dict(_cl_data(), inst=None)
    elif name == "F3_twii_dead_others_alive":   # 法人／期貨都在，只有 ^TWII 這個故障域全滅
        s["cl_data"] = _cl_data(inst=_INST)
        s["li_latest"] = _li((5000.0, 6000.0, 7000.0, 8000.0))
    elif name == "F4_health_legs_missing_adl_ok":  # ADL 還在、兩條腿都缺 → handlers 第三種擋燈理由
        s["cl_data"] = _cl_data(inst=_INST, adl=_ADL)
        s["li_latest"] = _li((5000.0, 6000.0, 7000.0, 8000.0))
    elif name == "N1_bull":
        s["cl_data"] = _cl_data(inst=_INST, adl=_ADL)
        s["mkt_info"] = {"score": 4, "max_score": 4, "regime": "bull",
                         "signals": ["站上MA120"], "index_price": 21500.0}
        s["jingqi_info"] = {"avg": 70.0}
        s["li_latest"] = _li((5000.0, 6000.0, 7000.0, 8000.0))
    elif name == "N2_trend_bear":        # 生效 regime=bear（分支 4）→ 油門被 regime 否決壓到防禦帶
        s["cl_data"] = _cl_data(inst=_INST, adl=_ADL)
        s["mkt_info"] = {"score": 2, "max_score": 4, "regime": "bear",
                         "signals": [], "index_price": 19800.0}
        s["jingqi_info"] = {"avg": 55.0}
        s["li_latest"] = _li((1000.0, -2000.0, 1500.0, -500.0))
    elif name == "N3_futures_defense":   # 外資期貨防禦（defense=True）
        s["cl_data"] = _cl_data(inst=_INST, adl=_ADL)
        s["mkt_info"] = {"score": 1, "max_score": 4, "regime": "neutral",
                         "signals": [], "index_price": 20100.0}
        s["jingqi_info"] = {"avg": 60.0}
        s["li_latest"] = _li((-38000.0, -39000.0, -41000.0, -40000.0))
    elif name == "N4_score_missing":     # 只缺大盤評分那條腿（health 仍算得出）
        s["cl_data"] = _cl_data(inst=_INST, adl=_ADL)
        s["jingqi_info"] = {"avg": 62.5}
        s["li_latest"] = _li((5000.0, 6000.0, 7000.0, 8000.0))
    elif name == "N5_health_zero":       # health 恰為 0.0（合法值，⛔ 當成缺值）
        s["cl_data"] = _cl_data(inst=_INST, adl=_ADL)
        s["mkt_info"] = {"score": 0, "max_score": 4, "regime": "neutral",
                         "signals": [], "index_price": 18000.0}
        s["jingqi_info"] = {"avg": 0.0}
        s["li_latest"] = _li((5000.0, 6000.0, 7000.0, 8000.0))
    else:  # pragma: no cover
        raise KeyError(name)
    return s


_FAIL = ("F1_all_failed", "F2_inst_none_legacy", "F3_twii_dead_others_alive",
         "F4_health_legs_missing_adl_ok")
_NORMAL = ("N1_bull", "N2_trend_bear", "N3_futures_defense", "N4_score_missing",
           "N5_health_zero")


def _patch_st(monkeypatch, fake, *mods) -> None:
    for _m in mods:
        monkeypatch.setattr(_m, "st", fake)


def _run_top(monkeypatch, state: dict, mod=STL, fake=None):
    """跑一次 `render_traffic_light_top()`；回 (回傳值, fake)。傳入 fake ＝ 沿用同一個 session（rerun）。"""
    fake = fake if fake is not None else _FakeST(state)
    _patch_st(monkeypatch, fake, mod, H, AS)
    monkeypatch.setattr(mod, "_dt", _FIXED_DT_MOD)
    ret = mod.render_traffic_light_top()
    return ret, fake


def _run_state(monkeypatch, state: dict):
    """跑一次 `render_section_state(..., show_market_data=True)`；回 fake。

    §二 尾端三件：燈號卡回填 → 🎚️ 建議持股油門 → 📖 為何這個顏色 —— 那正是 explainer 在 production
    的呼叫點（section_state 以 try/except 包住它）。燈號一律由 session 經 `load_section_inputs` 重算。
    ⚠️ 第一個參數（`_mkt_info`）一律傳 None ⇒ 拐點面板整段不跑（既有分支）。全敗（F*）時 tab_macro
    傳的本來就是 None；N* 時 production 會跑拐點面板，但那段會打 NDC／FinMind（與本批無關），fast lane
    不觸網，故略過 —— 比對的是同一段尾端輸出。
    """
    fake = _FakeST(state)
    _patch_st(monkeypatch, fake, SS, H, STL, MC, AS)
    ph = fake.empty()
    SS.render_section_state(None, ph, ph, state.get("cl_data") or {}, show_market_data=True)
    return fake


def _run_explainer(monkeypatch, tl, mod=MC):
    fake = _FakeST({})
    _patch_st(monkeypatch, fake, mod)
    mod.render_traffic_light_explainer(tl)
    return fake


def _tl_of(name: str):
    """該情境下 L2 `calc_traffic_light` 真的會回的 tl（與 section_state 同一條取數路徑）。"""
    from src.services import load_section_inputs
    inp = load_section_inputs(_scenario(name))
    return calc_traffic_light(inp.mkt_info or {}, inp.jingqi_info or {},
                              inp.cl_data or {}, inp.li_latest)


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=repr)


def _sha(obj) -> str:
    return hashlib.sha256(_canon(obj).encode("utf-8")).hexdigest()


def _top_digest(ret, fake) -> dict:
    return {"ret": [ret[1], ret[2]], "out": fake.out,
            "warroom": fake.session_state.get("warroom_summary"),
            "macro_state": fake.session_state.get("macro_state")}


def _undo(out, pairs):
    """把修後輸出中**唯一**預期改變的行換回修前寫法（每組新行必須恰好出現一次）。"""
    texts = [t for _, t in out]
    res = [list(x) for x in out]
    for new, old in pairs:
        hits = [i for i, t in enumerate(texts) if t == new]
        assert len(hits) == 1, f"預期恰好一行 {new!r}，實得 {len(hits)}"
        res[hits[0]][1] = old
    return [tuple(x) for x in res]


#: explainer 本批改到的兩行（修後 → 修前）。⚠️ 尾段的「切點」數字是上面釘住的門檻。
_H_NEW = "- 健康評分:**— 未取得** / 100  *(切點:35 → 防禦級)*"
_H_OLD = "- 健康評分:**None** / 100  *(切點:35 → 防禦級)*"
_S_NEW = "- 市場分數:**— 未取得** / 6  *(切點:多頭需 ≥ 4)*"
_S_OLD = "- 市場分數:**None** / 6  *(切點:多頭需 ≥ 4)*"

#: 頂卡（handlers 既有字）：擋燈標題、三種擋燈理由、已請求時的紅字 CTA。
_CARD_TITLE = "⏸️ 資料不足，無法判斷市場狀態"
_REASON_TWII = "大盤價格來源(^TWII)全滅 — 沒有價格骨幹就判不出趨勢"
_REASON_LEGS = "健康評分的兩條腿(大盤趨勢評分 / 旌旗指數)都缺 — 算不出健康度"
_CTA_FAILED = "重按「🚀 一鍵更新全部數據」對這個原因無效"
_REASON_BY_FAIL = {"F1_all_failed": _REASON_TWII, "F2_inst_none_legacy": _REASON_TWII,
                   "F3_twii_dead_others_alive": _REASON_TWII,
                   "F4_health_legs_missing_adl_ok": _REASON_LEGS}
#: 油門卡（section_traffic_light 既有字）
_THROTTLE_IDLE = "⬜ 建議持股油門：總經未評估 — 請先按「🚀 一鍵更新全部數據」"

#: 畫面上不該出現的缺值字（以「整個 token」比對：`NoneType` 等不算）。
_LEAK = re.compile(r"(?<![A-Za-z_])(None|nan|NaN|inf|null)(?![A-Za-z_])")


# ══════════════════════════════════════════════════════════════════════════
# golden（基底 24bf2af 實跑寫死；修後實跑寫死者另標明）
# ══════════════════════════════════════════════════════════════════════════
#: 有值時 `render_traffic_light_top` 的整份輸出＋warroom＋macro_state＋回傳值（基底 24bf2af；修後逐位相同）。
_BASE_TOP_SHA = {
    "N1_bull": "edff7264989decc4af866a804c88a09b93289e41cd563562e1875504611c7011",
    "N2_trend_bear": "704a6c685b8b8cfa9669563cc84a19406c00e9724c7e611e362c6929d308f7ed",
    "N3_futures_defense": "fe96c00fb93c9b21639341d09a6bc494f8c89fbde55d0ae45554f810e72690e5",
    "N4_score_missing": "d6e1c2903ac3f82032e3de7ff605ba0b443bbc29e152087a2e840533eada48d6",
    "N5_health_zero": "f7c67051eb13f50276632f7b2d33809b96c8f731f1f75955d86f6bed9ea4e12f",
}
#: 有值時寫進 warroom 的 throttle（基底 24bf2af 實跑原值）。N2／N3 驗 regime／defense 否決有傳進去，
#: N5 驗 health=0.0 照樣計算（0 不是缺值）。
_BASE_THROTTLE = {
    "N1_bull": {"lo_pct": 80, "hi_pct": 100, "mid_pct": 90, "posture": "積極", "icon": "🟢",
                "regime_capped": False},
    "N2_trend_bear": {"lo_pct": 0, "hi_pct": 20, "mid_pct": 10, "posture": "防禦(總經否決)",
                      "icon": "🔴", "regime_capped": True},
    "N3_futures_defense": {"lo_pct": 0, "hi_pct": 20, "mid_pct": 10, "posture": "防禦(總經否決)",
                           "icon": "🔴", "regime_capped": True},
    "N4_score_missing": {"lo_pct": 50, "hi_pct": 70, "mid_pct": 60, "posture": "中性偏多",
                         "icon": "🟡", "regime_capped": False},
    "N5_health_zero": {"lo_pct": 0, "hi_pct": 20, "mid_pct": 10, "posture": "防禦", "icon": "🔴",
                       "regime_capped": False},
}
#: 缺值時 `render_traffic_light_top` 的整份輸出＋warroom＋macro_state＋回傳值。
#: ⚠️ 修後碼實跑寫死（修前在這四個情境是拋例外，沒有輸出可比）。F1＝F2：inst None 與 {} 同義。
_FIXED_TOP_SHA = {
    "F1_all_failed": "e68a9238c7fb504ce8e1183abbd61e6aad20d7cd296f9fcd3d6a18a2e7251431",
    "F2_inst_none_legacy": "e68a9238c7fb504ce8e1183abbd61e6aad20d7cd296f9fcd3d6a18a2e7251431",
    "F3_twii_dead_others_alive": "2d693ea63ba08477c41054e483b51f9721d4d930c68ba4eda9a7a2003ac26e68",
    "F4_health_legs_missing_adl_ok": "ce591e0d557a3cf0a009a873297f7f1a1e777f4ebd4d359516a38a77b51867b5",
}
#: §二 尾端（燈號卡→油門→explainer）整份輸出（基底 24bf2af）。F*／N4 的修後輸出經 `_undo` 後須等於此值。
#: ⚠️ F* 這四個值含檔頭「範圍外」第 2 點那段截斷（explainer 規則表在 health=None 時拋例外、被 section_state
#:    吞掉）—— 本批 ⛔ 修那一點，故修前修後都截在同一處。日後修它時這四個 golden 須同步更新：那是預期的改變，
#:    ⛔ 當成回歸；也 ⛔ 拿本 golden 當「規則表本來就該截斷」的依據。
_BASE_STATE_SHA = {
    "F1_all_failed": "4517d076dcc7b51a3cda01d95f5b79478509fff9a0f7e2a3f02b27acdf88d95e",
    "F2_inst_none_legacy": "4517d076dcc7b51a3cda01d95f5b79478509fff9a0f7e2a3f02b27acdf88d95e",
    "F3_twii_dead_others_alive": "74b3278c0c6bb8877c739b780b6c2ac0e17e016ef86d170d1ae74b0d27f77689",
    "F4_health_legs_missing_adl_ok": "3e4b977b4675e2e49f8db8af20f88afa08ab5b11d42d9f9f36664f285cbe0ba9",
    "N1_bull": "5d2d84c86a09c19e8f4594485f6ea0cf96a01f71d17c9887c79433d6e9fcac90",
    "N2_trend_bear": "5ca07a68cf2f1cd495b37e0dcc5687ba388dc51e3d696ef3873abd04b00e83dd",
    "N3_futures_defense": "59a1360979cecd8aa3dc6685d9ec1ed7637a771164aeb01911716decd9b7ca99",
    "N4_score_missing": "78574489a1e1ea988982acef3721d9dcd743e3e7d9a1ed430d11ad6f365fe080",
    "N5_health_zero": "ce0a09448fe1ec350c89e0e024a24097b86eacfda3fd6018e725566b78519594",
}
#: explainer 單獨呼叫的整份輸出（基底 24bf2af）。N4 為修前（市場分數印 None）—— 修後經 `_undo` 後須等於此值。
_BASE_EXPL_SHA = {
    "N1_bull": "363d79d82087ef4b5c8da8d66041b52d6b346636384c59beb5f68861cd0b9546",
    "N2_trend_bear": "f72c9eb2d1524875deaf13d72750d8429345a0769180e618dba781c411db4ec0",
    "N3_futures_defense": "5985f15c9cf0de68482adf4e0919881eab7219bf350e7095cda134e51e419332",
    "N4_score_missing": "ac7671c889bb40b8a3ec91e410b0fb1e674af3b4421336d347411965365d306e",
    "N5_health_zero": "e113be03885b3360d4438c21a010ecb3a428436ad7393cf598b2dca82a322e6c",
    "fx_int_bear": "b6448704f91a727b54b05e5a26c50e34eb2af2cd33a7a14f9684fded29a1454d",
    "fx_int_bull": "1ee630ef8ce4e9875543c7bafb1c08743f2e599ec06e8c7dc5598c90372584b5",
    "fx_zero_int": "e6b094604cb98b0cbf80c808eb625bb67ef5759515e2a1e573ab952a3128609d",
    "fx_half": "93435b9ff0ffebd4fbf599d34a4fc819e094a1dbf1a1fe34b71a12eb2b877118",
}

#: explainer 舊 fixture 形狀（`tests/test_macro_classroom.py` 同型：整數值；另加 0／0 與 .5）。
_FX = {
    "fx_int_bear": {"color": "#f85149", "label": "空頭防禦｜降低部位", "health": 25, "score": 1,
                    "regime": "bear", "defense": True, "fut_net": -45000, "conf": 85},
    "fx_int_bull": {"color": "#3fb950", "label": "多頭市場｜積極操作", "health": 72, "score": 5,
                    "regime": "bull", "defense": False, "fut_net": 35000, "conf": 95},
    "fx_zero_int": {"color": "#f85149", "label": "x", "health": 0, "score": 0,
                    "regime": "neutral", "defense": False, "fut_net": None, "conf": 60},
    "fx_half": {"color": "#d29922", "label": "y", "health": 45.5, "score": 2.5,
                "regime": "bull", "defense": False, "fut_net": 0.0, "conf": 80},
}


def _texts(fake) -> list[str]:
    return [t for _, t in fake.out]


# ══════════════════════════════════════════════════════════════════════════
# ① section_traffic_light：全敗（health=None）不再炸頁
# ══════════════════════════════════════════════════════════════════════════
class TestTopAllFailedNoLongerRaises:
    """F1～F4：修前 `float(None)` → TypeError（整頁紅框）；修後畫既有擋燈卡、throttle 寫 None。"""

    @pytest.mark.parametrize("name", _FAIL)
    def test_renders_the_existing_blocked_card(self, _pinned, name):
        ret, fake = _run_top(_pinned, _scenario(name))
        assert (ret[1], ret[2]) == (True, "unknown")
        assert len(fake.out) == 1, fake.out
        kind, card = fake.out[0]
        assert kind == "markdown"
        assert _CARD_TITLE in card
        assert f"（{_REASON_BY_FAIL[name]}）" in card
        # 已按過更新 ⇒ 紅字指路（handlers 既有 UI_FAILED 那支），⛔ 退回「⬜ 尚未載入」閒置文案
        assert _CTA_FAILED in card
        assert "⬜ 尚未載入" not in card
        assert not _LEAK.search(re.sub(r"<[^>]+>", " ", card))

    @pytest.mark.parametrize("name", _FAIL)
    def test_throttle_is_none_not_a_fabricated_band(self, _pinned, name):
        """§1：health 沒有 ⇒ 油門也沒有。⛔ 補 0（0 分在油門表是「防禦 0–20%」＝捏一個最強利空）。"""
        _, fake = _run_top(_pinned, _scenario(name))
        wr = fake.session_state["warroom_summary"]
        assert wr["throttle"] is None
        assert wr["health_score"] is None
        assert (wr["effective_regime"], wr["light"], wr["regime_source"]) == (
            "unknown", "⬜", "unloaded")
        assert fake.session_state["macro_state"]["is_loaded"] is False

    @pytest.mark.parametrize("name", _FAIL)
    def test_whole_output_golden(self, _pinned, name):
        ret, fake = _run_top(_pinned, _scenario(name))
        assert _sha(_top_digest(ret, fake)) == _FIXED_TOP_SHA[name]

    def test_rerun_within_fresh_window_stays_rendered(self, _pinned):
        """快取新鮮的 30 分鐘內每次 rerun 修前都再炸一次。第二輪讀第一輪寫的 warroom
        （`jingqi_avg=None` ⇒ `load_section_inputs` 合成 `{'avg': None}`）—— 修後每一輪輸出相同。"""
        _, fake = _run_top(_pinned, _scenario("F1_all_failed"))
        first = list(fake.out)
        fake.out.clear()
        ret, fake = _run_top(_pinned, {}, fake=fake)
        assert fake.out == first
        assert (ret[1], ret[2]) == (True, "unknown")
        assert fake.session_state["warroom_summary"]["throttle"] is None

    def test_allocation_and_regime_stay_unloaded(self, _pinned):
        """warroom 這次寫進去了（health_score=None），全站持股 SSOT 與 regime 契約仍回「未評估」——
        與修前（warroom 根本沒寫）是同一個答案（`get_macro_state` 對非有限 health_score 視同未載入）。"""
        _, fake = _run_top(_pinned, _scenario("F1_all_failed"))
        alloc = AS.get_allocation()
        assert (alloc.is_loaded, alloc.range_text) == (False, "--")
        reg = AS.get_macro_regime()
        assert (reg["is_loaded"], reg["regime"], reg["light"]) == (False, "unknown", "⬜")
        # 拿掉 warroom（＝修前那一輪的 session）重算 → 決策逐欄相同
        fake.session_state.pop("warroom_summary")
        for _k in (AS._ALLOC_CACHE_KEY, AS._ALLOC_SIG_KEY):
            fake.session_state.pop(_k, None)
        assert AS.get_allocation() == alloc
        assert AS.get_macro_regime() == reg


class TestTopWithValuesUnchanged:
    """N1～N5（health 有值，含 0.0）：整份輸出、warroom、macro_state、回傳值與基底逐位相同。"""

    @pytest.mark.parametrize("name", _NORMAL)
    def test_whole_output_identical_to_base(self, _pinned, name):
        ret, fake = _run_top(_pinned, _scenario(name))
        assert _sha(_top_digest(ret, fake)) == _BASE_TOP_SHA[name]

    @pytest.mark.parametrize("name", _NORMAL)
    def test_throttle_still_computed_with_same_arguments(self, _pinned, name):
        _, fake = _run_top(_pinned, _scenario(name))
        assert fake.session_state["warroom_summary"]["throttle"] == _BASE_THROTTLE[name]


# ══════════════════════════════════════════════════════════════════════════
# ② macro_classroom：📖 為何紅綠燈是現在這個顏色 —— None 改印「— 未取得」
# ══════════════════════════════════════════════════════════════════════════
class TestExplainerShowsNotObtained:

    @pytest.mark.parametrize("name", _FAIL)
    def test_production_caller_prints_not_obtained(self, _pinned, name):
        """走 production 呼叫點（§二 尾端，section_state 以 try/except 包住 explainer）。"""
        fake = _run_state(_pinned, _scenario(name))
        texts = _texts(fake)
        assert _H_NEW in texts and _S_NEW in texts
        assert not any("**None**" in t for t in texts)
        assert _THROTTLE_IDLE in texts                       # 油門卡：既有「總經未評估」
        assert any(_CARD_TITLE in t for t in texts)          # 燈號卡：既有擋燈卡
        # 除了這兩行，整份輸出與基底逐字相同
        assert _sha(_undo(fake.out, [(_H_NEW, _H_OLD), (_S_NEW, _S_OLD)])) == \
            _BASE_STATE_SHA[name]

    def test_only_score_missing(self, _pinned):
        """只缺大盤評分那條腿（修前在 production 就看得到「市場分數:**None** / 6」）。"""
        fake = _run_explainer(_pinned, _tl_of("N4_score_missing"))
        texts = _texts(fake)
        assert _S_NEW in texts
        assert "- 健康評分:**62.5** / 100  *(切點:35 → 防禦級)*" in texts
        assert not any("**None**" in t for t in texts)
        assert _sha(_undo(fake.out, [(_S_NEW, _S_OLD)])) == _BASE_EXPL_SHA["N4_score_missing"]
        fake2 = _run_state(_pinned, _scenario("N4_score_missing"))
        assert _sha(_undo(fake2.out, [(_S_NEW, _S_OLD)])) == _BASE_STATE_SHA["N4_score_missing"]

    @pytest.mark.parametrize("name", [n for n in _NORMAL if n != "N4_score_missing"])
    def test_values_unchanged(self, _pinned, name):
        assert _sha(_run_explainer(_pinned, _tl_of(name)).out) == _BASE_EXPL_SHA[name]
        assert _sha(_run_state(_pinned, _scenario(name)).out) == _BASE_STATE_SHA[name]

    @pytest.mark.parametrize("name", sorted(_FX))
    def test_values_unchanged_fixture_shapes(self, _pinned, name):
        assert _sha(_run_explainer(_pinned, _FX[name]).out) == _BASE_EXPL_SHA[name]

    def test_zero_is_a_value_not_missing(self, _pinned):
        """判 `is not None`、⛔ 用 `or`：健康 0／市場分數 0 是真的值，照印 0。"""
        texts = _texts(_run_explainer(_pinned, _FX["fx_zero_int"]))
        assert "- 健康評分:**0** / 100  *(切點:35 → 防禦級)*" in texts
        assert "- 市場分數:**0** / 6  *(切點:多頭需 ≥ 4)*" in texts
        texts = _texts(_run_explainer(_pinned, _tl_of("N5_health_zero")))
        assert "- 健康評分:**0.0** / 100  *(切點:35 → 防禦級)*" in texts
        assert "- 市場分數:**0.0** / 6  *(切點:多頭需 ≥ 4)*" in texts

    def test_not_obtained_is_an_existing_phrase(self):
        """K1：本批沒有新字 —— 「— 未取得」在修前同檔已用於 regime 兩行（逐字）。"""
        src = pathlib.Path(MC.__file__).read_text(encoding="utf-8")
        assert "**{_trend_regime or '— 未取得'}**" in src
        assert "**{_eff_regime or '— 未取得'}**" in src


# ══════════════════════════════════════════════════════════════════════════
# 修前重現（還原體）—— 字面錨點，⛔ 不算殺突變
# ══════════════════════════════════════════════════════════════════════════
_STL_FIX = ("        _wr_throttle = None\n"
            "        if _tl_init['health'] is not None:\n"
            "            _wr_throttle = compute_position_throttle(\n"
            "                float(_tl_init['health']), regime=_tl_eff_reg,\n"
            "                defense=bool(_tl_init.get('defense')))\n")
_STL_PRE = ("        _wr_throttle = compute_position_throttle(\n"
            "            float(_tl_init['health']), regime=_tl_eff_reg,\n"
            "            defense=bool(_tl_init.get('defense')))\n")
_MC_REVERT = (('f"- 健康評分:**{_health_txt}** / 100"', 'f"- 健康評分:**{_health}** / 100"'),
              ('f"- 市場分數:**{_score_txt}** / 6"', 'f"- 市場分數:**{_score}** / 6"'))


def _load_variant(mod, pairs, tag: str):
    """把模組原始碼做「恰好一處」的字面替換後，載成獨立模組（不進 `sys.modules`、不碰本尊）。"""
    code = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    for old, new in pairs:
        assert code.count(old) == 1, f"替換點不唯一或已不存在：{old!r}"
        code = code.replace(old, new)
    spec = importlib.util.spec_from_loader(f"_z8_{tag}", loader=None)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = mod.__file__
    exec(compile(code, mod.__file__, "exec"), m.__dict__)
    return m


class TestRevertedIsTheBug:
    """正式碼換回 24bf2af 寫法 → 上面各類應轉紅的那個病，在這裡實際重現一次。"""

    @pytest.mark.parametrize("name", _FAIL)
    def test_reverted_top_raises_the_reported_error(self, _pinned, name):
        pre = _load_variant(STL, [(_STL_FIX, _STL_PRE)], "stl_pre")
        with pytest.raises(TypeError, match=r"float\(\) argument must be a string or a real "
                                            r"number, not 'NoneType'"):
            _run_top(_pinned, _scenario(name), mod=pre)

    def test_reverted_explainer_prints_none(self, _pinned):
        pre = _load_variant(MC, _MC_REVERT, "mc_pre")
        _pinned.setattr(pre, "HEALTH_DEFENSE_THRESHOLD", _PIN_HEALTH_DEFENSE)
        _pinned.setattr(pre, "BULL_MIN_SCORE", _PIN_BULL_MIN)
        fake = _run_explainer(_pinned, _tl_of("N4_score_missing"), mod=pre)
        assert _S_OLD in _texts(fake)
        assert _sha(fake.out) == _BASE_EXPL_SHA["N4_score_missing"]


# ══════════════════════════════════════════════════════════════════════════
# slow lane —— 真 Streamlit（AppTest）
# ══════════════════════════════════════════════════════════════════════════
#: 「全敗後」session（A 組實跑後讀到的形狀：mkt_info／jingqi_info／li_latest／warroom 都不在）。
_PRESET = ("import datetime as _dtm\n"
           "if 'z8_init' not in st.session_state:\n"
           "    st.session_state['z8_init'] = True\n"
           "    st.session_state['cl_data'] = dict(intl={}, tw={}, tech={}, inst={},\n"
           "                                       inst_date=None, margin=None, adl=None)\n"
           "    st.session_state['cl_ts'] = _dtm.datetime.now().strftime('%Y-%m-%d %H:%M')\n"
           "    st.session_state['chips_loaded'] = True\n"
           "    st.session_state['_is_refreshing'] = False\n")
_TOP_ONLY = ("from src.ui.tabs.macro.section_traffic_light import render_traffic_light_top\n"
             "render_traffic_light_top()\n")
#: 整個總經分頁，外層包 app.py 的 `_render_tab_isolated`（AST 抽出原文，⛔ 照抄一份）。
_WHOLE_TAB = ("import ast as _ast\n"
              "from shared.secret_md import scrub_md as _scrub\n"
              "_app_src = open(" + repr(str(_REPO / "app.py")) + ", encoding='utf-8').read()\n"
              "_fn = next(n for n in _ast.parse(_app_src).body\n"
              "           if isinstance(n, _ast.FunctionDef) and n.name == '_render_tab_isolated')\n"
              "_ns = {'st': st, 'scrub_md': _scrub}\n"
              "exec(compile(_ast.Module(body=[_fn], type_ignores=[]), 'app.py', 'exec'), _ns)\n"
              "from src.ui.tabs import render_tab_macro\n"
              "_ns['_render_tab_isolated'](render_tab_macro, '總經')\n")
_END = "st.markdown('Z8_SCRIPT_END')\n"
#: app.py 紅框的固定字（`_render_tab_isolated`）。
_RED_BOX = "分頁渲染異常,已隔離"


@pytest.fixture
def _offline(monkeypatch, tmp_path):
    """slow lane：全部來源失敗（見 `_deny_network`）＋ `st.cache_data` 前後清空。"""
    import streamlit as _st
    denied = _deny_network(monkeypatch, tmp_path)
    _st.cache_data.clear()
    yield denied
    _st.cache_data.clear()


def _app(body: str):
    pytest.importorskip("streamlit.testing.v1")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_string(
        "import sys\n"
        f"sys.path.insert(0, {str(_REPO)!r})\n"
        "import streamlit as st\n" + body, default_timeout=180)
    at.secrets["FINMIND_TOKEN"] = ""
    return at


def _ok(at) -> None:
    if at.exception:
        pytest.fail("render 有 uncaught exception:\n" + "\n".join(
            f"{e.type}: {str(e.value)[:300]}" for e in at.exception))


def _all_text(at) -> list[str]:
    """畫面上所有文字元素（含 expander 內）＋ expander／按鈕標籤。"""
    out: list[str] = []
    for coll in ("markdown", "caption", "info", "warning", "error", "success", "text",
                 "title", "header", "subheader", "code"):
        for el in getattr(at, coll, []):
            out.append(str(el.value))
    for el in at.expander:
        out.append(str(el.label))
    for el in at.metric:
        out.extend([str(el.label), str(el.value)])
    return out


def _has(at, key: str) -> bool:
    try:
        at.session_state[key]
    except Exception:  # noqa: BLE001 — AppTest 缺鍵時拋 KeyError／AttributeError
        return False
    return True


#: 既有 L1 診斷 token（範圍外，⚠️ 單組發現，已回報）：`macro_snapshot.py` 約 L1089
#: `f'stat.gov.tw:HTTP {getattr(_r_stat, "status_code", None)}'` 在沒拿到回應時組出「HTTP None」，
#: 由 §八 失敗原因清單（`section_mid.py` 約 L321 `_err_export`）原樣列出。只在抓取段真的跑過時出現
#: （③ 才有；①② 的預置 session 沒有 macro_info）。掃缺值字前只剔除這一個 token，其餘一律照掃。
_KNOWN_L1_TOKENS = ("stat.gov.tw:HTTP None",)


def _assert_rendered_after_all_failed(at, *, known_tokens=()) -> None:
    texts = _all_text(at)
    blob = "\n".join(texts)
    assert not [e.value for e in at.error if _RED_BOX in e.value], "整頁仍被換成紅框"
    assert "Z8_SCRIPT_END" in texts, "腳本沒跑到底"
    assert _CARD_TITLE in blob                                   # 頂卡：既有擋燈卡
    assert _CTA_FAILED in blob
    assert "建議持股油門：總經未評估 — 請先按「🚀 一鍵更新全部數據」" in blob   # 油門卡：既有字
    assert any(t.startswith("- 健康評分:**— 未取得** / 100") for t in texts)
    assert any(t.startswith("- 市場分數:**— 未取得** / 6") for t in texts)
    leaks = []
    for t in texts:
        for tok in known_tokens:
            t = t.replace(tok, "")
        if _LEAK.search(re.sub(r"<[^>]+>", " ", t)):
            leaks.append(t)
    assert not leaks, f"畫面出現缺值字：{leaks[:3]}"
    wr = at.session_state["warroom_summary"]
    assert wr["health_score"] is None and wr["throttle"] is None


@pytest.mark.slow
class TestRealStreamlitZ8:

    def test_minimal_repro_top_only(self, _offline):
        """最小重現：預置「全敗後」session → `render_traffic_light_top()`；第二輪＝rerun。"""
        at = _app(_PRESET + _TOP_ONLY + _END)
        for _ in range(2):
            at.run()
            _ok(at)
            assert any(m.value == "Z8_SCRIPT_END" for m in at.markdown)
            assert any(_CARD_TITLE in m.value and _CTA_FAILED in m.value for m in at.markdown)
            assert at.session_state["warroom_summary"]["throttle"] is None

    def test_whole_tab_preset_session(self, _offline):
        """整個總經分頁（外層＝app.py 的隔離包裝原文）：修前整頁紅框；修後照常渲染到底。"""
        at = _app(_PRESET + _WHOLE_TAB + _END)
        for _ in range(2):
            at.run()
            _ok(at)
            _assert_rendered_after_all_failed(at)

    def test_click_refresh_with_every_source_failing(self, _offline, monkeypatch):
        """mock 全部來源失敗後按「🚀 一鍵更新全部數據」：真的抓取段 → `st.rerun` → 最終畫面。"""
        import src.services.macro_fetch_orchestrator as MFO
        _real = MFO.fetch_macro_bundle
        li_seen: list = []

        def _bundle(**kw):
            b = _real(**kw)
            # 先行指標 job「逾時 → None」（A 組真網路實跑的形狀：li_latest 不存在）。⚠️ 它若回
            # 「14 列、數值全 None」，頁面會在 section_chips 約 L266 拋同一句 TypeError（C8-n1 (a)，
            # 範圍外，見檔頭）—— 那不是本批這個拋出點，故在此固定成 None、只驗本批。
            li_seen.append(type(b.get("df_li_a")).__name__)
            b["df_li_a"] = None
            return b
        monkeypatch.setattr(MFO, "fetch_macro_bundle", _bundle)

        at = _app(_WHOLE_TAB + _END)
        at.run()
        _ok(at)
        at.button(key="cl_refresh").click().run()     # 冷啟動第一下只設旗標（C9-n3，範圍外）
        _ok(at)
        assert not li_seen, "第一下就抓了 —— 與 C9-n3 的現況不符，請重看本測試的前提"
        at.button(key="cl_refresh").click().run()     # 第二下：真的抓（全部失敗）→ st.rerun
        _ok(at)
        # 前提：真的走過抓取段、連線真的全被拒絕，而且得到的是「全敗後」的 session
        assert li_seen, "沒有走到抓取段"
        assert _offline, "沒有任何對外連線被拒絕 —— 不是「全部來源失敗」"
        assert _has(at, "cl_ts") and _has(at, "cl_data")
        assert not _has(at, "mkt_info") and not _has(at, "jingqi_info")
        _assert_rendered_after_all_failed(at, known_tokens=_KNOWN_L1_TOKENS)
        # 使用者再點一下頁面（快取新鮮期內的 rerun）：仍照常
        at.run()
        _ok(at)
        _assert_rendered_after_all_failed(at, known_tokens=_KNOWN_L1_TOKENS)
