"""src/services/reconcile_service.py — §4.3 雙演算法／雙源對帳的 L3 wrapper（批 Z56）。

給新 UI「📖 憑什麼 › 資料體檢 › 進階診斷」的「雙演算法對帳（§4.3）」卡用。
對帳本身是 L2 `src/compute/risk/reconcile.py` 的純函式（本檔一行算式都不寫）；
本檔只負責**從傳進來的 session mapping 取輸入**，並在交給 L2 之前**先擋無效數值**。

§8.2：L3 Service。**純讀**呼叫端傳入的 mapping —— ⛔ 不 import streamlit、⛔ 不 import 舊面板 L5
（`src/ui/pages/reconcile_panel.py`）、零網路、零 L1。

── 取值規則（移植自舊面板 `reconcile_panel._get_us10y_pair` / `_get_health_params`）────────────
與舊面板**同輸入逐列相同**（守衛：`tests/test_batch_z56.py` 直接拿舊面板 `compute_reconcile_rows`
對帳），只有兩處刻意不同：

1. **旌旗指數 `jqavg` 改為 `jingqi_info` 優先**（`warroom_summary['jingqi_avg']` 只在 `jingqi_info`
   不存在或為假值（如 `None`、空 dict）時才用；`jingqi_info` 為真值但沒有 `avg` ⇒ 缺值，⛔ 不退回 warroom）。
   📌 批 Z58（Z57-n1，事實更正）：Z57 寫「不存在或為空（`None`、空 dict）」仍不精確 ——
   `if _jq_info:` 對**任何假值**（`0`、`""`、`[]`…）都改讀 warroom，故改為「假值」措辭；程式行為未動。
   📌 批 Z57（有意識的更正，⛔ 不是漏刪）：原句「只在 `jingqi_info` 不存在時才用」與程式條件
   `if _jq_info:` 不符（空 dict 也會改讀 warroom）—— 只改文字使其屬實，程式行為未動。理由：新 UI「🚀 更新今日戰情」（L3 `macro_refresh_service.refresh_macro_now`）
   會寫 `jingqi_info`、**不寫** `warroom_summary`；舊面板先讀 warroom，會吃到舊「🌍 總經」分頁
   留下的舊值。優先序與 L3 `section_inputs.build_section_inputs` 一致。
   📌 批 Z62（Z60 更正；有意識的更正，⛔ 不是漏刪 —— 上面那句保留，它在寫下的當天為真）：
   ~~新 UI「🚀 更新今日戰情」**不寫** `warroom_summary`~~ 自批 Z60 起已不成立 —— 該路徑的
   `STEP_WARROOM`（L3 `warroom_apply.compute_and_store_warroom_summary`）會寫 `warroom_summary`。
   **`jingqi_info` 優先的處置不變**，理由改為：`jingqi_info` 是旌旗指數的**來源**，
   `warroom_summary['jingqi_avg']` 是由它（或上一份 warroom）**推導出來的結論**，可能落後一輪
   或來自舊「🌍 總經」分頁 —— 來源在時以來源為準（程式行為未動，只改註解）。
2. **每個輸入先過 `shared.station_specs.is_invalid_number`**（客戶 2026-10-13 裁示 B）：
   NaN／±inf／轉不成數字 ⇒ 該列**不交給 L2**、不出數值、不判一致與否，只帶項目名
   （畫面說明一律 `{項目}資料異常，無法計算，不下結論。`）。
   不先擋的後果（L2 本身不防）：FRED 為 NaN 時 `reconcile_pair` 得 `disagree`（假紅）；
   外資 net 為 NaN／inf 時 `fnet > 0` 判斷照走，`agree` 靜默通過（假綠）。

── 月營收 YoY 那一列 ────────────────────────────────────────────────
`t2_data['rev_yoy_self']` / `t2_data['rev_yoy_finmind']` 全 repo **0 個寫入點**（舊面板自己註「預留欄位」；
守衛：`tests/test_batch_z56.py::test_rev_yoy_keys_still_have_no_writer`）。本檔照舊面板讀這兩個 key，
所以這一列在 production 一律是兩邊皆缺 —— 畫面據實寫「沒有寫入者」，不顯示數值。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, NamedTuple, Optional

from shared.inst_net import is_net_observed  # 批 Z33：外資淨額未觀測（L1 預填／L3 補零推出）不當真值
from shared.station_specs import is_invalid_number
from src.compute.risk.reconcile import (
    reconcile_health_score,
    reconcile_monthly_revenue_yoy,
    reconcile_us10y_yield,
)

#: 舊面板同名常數（`reconcile_panel._MAX_SCORE_FALLBACK`）：必須與
#: `macro_helpers.calc_traffic_light` 健康段的 `float(_mkt.get('max_score') or 4.0)` 同值。
MAX_SCORE_FALLBACK: float = 4.0

#: 三列的列名（舊面板 `compute_reconcile_rows` 的 `name` 原文，⛔ 不新造）。
ROW_US10Y: str = "US10Y 殖利率"
ROW_REV_YOY: str = "月營收 YoY(待個股觸發)"
ROW_HEALTH: str = "健康評分(v1 vs v2)"

#: 資料異常時的項目名（＝ `INVALID_DATA_TEXT` 的 `{item}`）。一律是 repo 既有字串：
#: 「10Y公債殖利率」＝ `cl_data['intl']` 的既有鍵名；「旌旗指數」「大盤評分」「外資」為總經頁既有用語；
#: 「月營收 YoY」取自舊面板列名。
ITEM_US10Y: str = "10Y公債殖利率"
ITEM_REV_YOY: str = "月營收 YoY"
ITEM_JINGQI: str = "旌旗指數"
ITEM_MKT_SCORE: str = "大盤評分"
ITEM_FOREIGN: str = "外資"


class SessionRead(NamedTuple):
    """對帳讀的一組 session 值（批 Z57）。

    Attributes:
        row: 讀這組值的對帳列（`ROW_*`）。
        keys: 這組值用到的**頂層** session key（`compute_reconcile` 對傳入 mapping 直接 `.get` 的 key）。
        desc: 子鍵描述（畫面「為什麼」逐字引用；條件分支照程式行為寫）。
    """

    row: str
    keys: tuple[str, ...]
    desc: str


#: 批 Z57（Z56-n2）：`compute_reconcile` 讀的 session 值 —— **唯讀 SSOT**（tuple，依對帳列順序：
#: US10Y → 月營收 YoY → 健康評分）。新 UI「📖 憑什麼」對帳卡灰態的「為什麼」由它組出
#: （`page_why.reconcile_not_triggered_why`），⛔ 不在 L5 另寫一份 key 清單。
#: 守衛：`tests/test_batch_z57.py` 以記錄式假 session 實跑各分支 —— 實際讀到的頂層 key ⊆ 本常數、
#: 本常數每個 key 都會被讀到（無死條目）、每列讀的 key 與該列條目相等。
RECONCILE_SESSION_KEYS: tuple[SessionRead, ...] = (
    SessionRead(ROW_US10Y, ("macro_info",), "`macro_info['us10y']['value']`"),
    SessionRead(ROW_US10Y, ("cl_data",), "`cl_data['intl']['10Y公債殖利率']`"),
    SessionRead(ROW_REV_YOY, ("t2_data",),
                "`t2_data['rev_yoy_self']`／`t2_data['rev_yoy_finmind']`"),
    SessionRead(ROW_HEALTH, ("jingqi_info", "warroom_summary"),
                "`jingqi_info['avg']`（`jingqi_info` 不存在或為假值（如 `None`、空 dict）時改讀 "
                "`warroom_summary['jingqi_avg']`）"),
    SessionRead(ROW_HEALTH, ("mkt_info",), "`mkt_info['score']`、`mkt_info['max_score']`"),
    SessionRead(ROW_HEALTH, ("cl_data",), "`cl_data['inst']` 外資 net"),
)


@dataclass(frozen=True)
class ReconcileRow:
    """一列對帳。

    Attributes:
        name: 列名（舊面板原文）。
        result: L2 `reconcile_pair` 標準回傳（`status` / `value_a` / `value_b` / `source_*` /
            `delta_abs` …）原樣。`invalid_items` 非空時為 `None`（⛔ 沒交給 L2）。
        invalid_items: 這一列哪幾個輸入是無效數值（依輸入順序、去重）。空 ＝ 沒有異常。
    """

    name: str
    result: Optional[dict] = None
    invalid_items: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReconcileReport:
    rows: tuple[ReconcileRow, ...] = ()

    @property
    def comparable(self) -> bool:
        """卡片判灰／綠的依據（QA D2）：任一列**有比對結果**（`agree`／`disagree`）或**資料異常**。
        三列全是 ⬜ 未觸發（缺至少一邊）且沒有異常列 ⇒ False（灰）。"""
        return any(_r.invalid_items or (_r.result or {}).get("status") in ("agree", "disagree")
                   for _r in self.rows)

    # 📌 批 Z56 收尾（有意識的刪除，⛔ 不是漏刪）：原有 `has_input`（任一輸入非 None）與
    #    `ReconcileRow.has_input` 欄位，因卡片改按 `comparable` 判灰／綠而成 0 引用（v3 §01-2 收尾）。


def _get(m: Any, key: str) -> Any:
    return m.get(key) if isinstance(m, Mapping) else None


def _dedupe(items) -> tuple[str, ...]:
    _out: list[str] = []
    for _i in items:
        if _i not in _out:
            _out.append(_i)
    return tuple(_out)


# ── 輸入：US10Y ──────────────────────────────────────────────────────
def us10y_inputs(session: Mapping[str, Any]) -> tuple[Any, Any]:
    """`(FRED DGS10, Yahoo ^TNX 原始報價)` —— **原值**（尚未判有效與否、尚未轉 float）。

    移植自舊面板 `_get_us10y_pair`：FRED 取 `macro_info['us10y']['value']`；^TNX 取
    `cl_data['intl']['10Y公債殖利率']` 的 `close`（或 `Close`）欄最後一筆。
    """
    _macro = session.get("macro_info", {}) or {}
    _cl = session.get("cl_data", {}) or {}
    _fred = (_macro.get("us10y") or {}).get("value")
    _intl = _cl.get("intl") or {}
    _tnx_df = _intl.get("10Y公債殖利率")
    _yahoo = None
    if _tnx_df is not None and hasattr(_tnx_df, "empty") and not _tnx_df.empty:
        _ccol = "close" if "close" in _tnx_df.columns else (
            "Close" if "Close" in _tnx_df.columns else None)
        if _ccol:
            try:
                _yahoo = _tnx_df[_ccol].iloc[-1]
            except Exception:   # noqa: BLE001 — 同舊面板：取不到 ⇒ 未取得
                _yahoo = None
    return _fred, _yahoo


def _to_float_or_none(v: Any) -> Optional[float]:
    """已確認 `is_invalid_number(v)` 為 False 的值 → float；`None`／空字串 → `None`。"""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return float(v)


def _us10y_row(session: Mapping[str, Any]) -> ReconcileRow:
    _fred_raw, _tnx_raw = us10y_inputs(session)
    if is_invalid_number(_fred_raw) or is_invalid_number(_tnx_raw):
        return ReconcileRow(ROW_US10Y, invalid_items=(ITEM_US10Y,))
    # 有效值才轉 float（舊面板 FRED 原樣交 L2、^TNX 先 float 再交 L2；有效數值兩者結果相同）。
    # QA D1：一律走 `_to_float_or_none` —— 空字串／空白視為缺值（該列 ⬜ 未觸發），⛔ 不讓 `float("")`
    #   的 ValueError 把整張卡變紅；轉不成數字的字串在上一行已由 `is_invalid_number` 判成資料異常。
    _r = reconcile_us10y_yield(_to_float_or_none(_fred_raw), _to_float_or_none(_tnx_raw))
    return ReconcileRow(ROW_US10Y, result=_r)


# ── 輸入：月營收 YoY ─────────────────────────────────────────────────
def _rev_yoy_row(session: Mapping[str, Any]) -> ReconcileRow:
    _t2 = session.get("t2_data", {}) or {}
    _self, _fm = _t2.get("rev_yoy_self"), _t2.get("rev_yoy_finmind")
    if is_invalid_number(_self) or is_invalid_number(_fm):
        return ReconcileRow(ROW_REV_YOY, invalid_items=(ITEM_REV_YOY,))
    # QA D1：同上，先轉 float（空字串 → 缺值），⛔ 不把字串原樣交 L2 做算術而把例外拋到卡層。
    return ReconcileRow(ROW_REV_YOY,
                        result=reconcile_monthly_revenue_yoy(_to_float_or_none(_self),
                                                             _to_float_or_none(_fm)))


# ── 輸入：健康評分 ───────────────────────────────────────────────────
def health_inputs(session: Mapping[str, Any]) -> dict[str, Any]:
    """健康評分對帳的**原值**：`jq` / `score` / `max_score` / `fnet`（尚未判有效與否、尚未換算）。

    · `jq`：`jingqi_info` 存在（非空）就**只用它**的 `avg` —— 沒有 `avg` 時該值為缺值，
      ⛔ 不退回 warroom（新 UI 路徑不寫 warroom，那裡可能是舊頁籤殘留的過期值；同
      `section_inputs.build_section_inputs`）；`jingqi_info` 不存在或為假值（如 `None`、空 dict）時才採用
      `warroom_summary['jingqi_avg']`（批 Z57 文字更正：原寫「不存在時」，與 `if _jq_info:` 不符；
      批 Z58 再更正：Z57 的「為空」不涵蓋 `0`／`""`／`[]` 等其他假值，改為「假值」）。
      📌 批 Z62（Z60 更正，上句保留不刪）：括號內「新 UI 路徑不寫 warroom」自批 Z60 起不成立
      （`STEP_WARROOM` 會寫 `warroom_summary`）；`jingqi_info` 優先仍維持 —— 它是來源，
      warroom 的 `jingqi_avg` 是推導出的結論、可能落後一輪或來自舊頁籤（程式行為未動）。
    · `score` / `max_score`：`mkt_info` 原值。
    · `fnet`：`cl_data['inst']` 第一個含「外資」的鍵的 `net`；**未觀測**（`is_net_observed` 為 False，
      L1 預填 0.0／L3 補零推出）⇒ `None`（同舊面板批 Z33）。
    """
    _wr = session.get("warroom_summary", {}) or {}
    _jq_info = session.get("jingqi_info")
    if _jq_info:
        _jq = _get(_jq_info, "avg")      # 沒有 avg ⇒ None（缺值），⛔ 不退回 warroom（可能是舊頁籤殘留）
        # 📌 批 Z62（Z60 更正，上行註解保留）：Z60 起新 UI 也會寫 warroom，但其 `jingqi_avg` 是由
        #   `jingqi_info`（或上一份 warroom）推導的結論 ⇒ 來源在時仍以 `jingqi_info` 為準（行為未動）。
    else:
        _jq = _get(_wr, "jingqi_avg")
    _mkt = session.get("mkt_info", {}) or {}
    _cl = session.get("cl_data", {}) or {}
    _inst = _cl.get("inst") or {}
    _fk = next((k for k in _inst if "外資" in str(k)), None)
    _fnet = (_inst.get(_fk, {}).get("net")
             if _fk and is_net_observed(_inst, _fk) else None)
    return {"jq": _jq, "score": _mkt.get("score"), "max_score": _mkt.get("max_score"),
            "fnet": _fnet}


def score_pct_from(score: Any, max_score: Any) -> Optional[float]:
    """`score` → 0~100（移植自舊面板，含 `or 4.0`（0 也退 4.0）、負分母回 `None`、上限夾 100）。

    呼叫前須已確認兩者都不是無效數值。
    """
    if score is None:
        return None
    try:
        _max = float(max_score or MAX_SCORE_FALLBACK)
    except (TypeError, ValueError):
        print(f"[reconcile_service] ⚠️ mkt_info['max_score'] 無法轉 float: {max_score!r}"
              " → score_pct 視為未取得(§1)")
        return None
    if _max < 0:
        print(f"[reconcile_service] ⚠️ mkt_info['max_score'] 為負: {_max!r}"
              " → score_pct 視為未取得(§1,不硬算出一個負百分比)")
        return None
    try:
        return min(float(score) / _max * 100.0, 100.0)
    except (TypeError, ValueError, ZeroDivisionError):
        print(f"[reconcile_service] ⚠️ score 無法換算: {score!r} → 視為未取得(§1)")
        return None


def _health_row(session: Mapping[str, Any]) -> ReconcileRow:
    _in = health_inputs(session)
    _bad: list[str] = []
    if is_invalid_number(_in["jq"]):
        _bad.append(ITEM_JINGQI)
    # max_score 只在 score 有值時才進算式（同舊面板）⇒ 只在那時才算「影響結論」。
    if is_invalid_number(_in["score"]) or (
            _in["score"] is not None and is_invalid_number(_in["max_score"])):
        _bad.append(ITEM_MKT_SCORE)
    if is_invalid_number(_in["fnet"]):
        _bad.append(ITEM_FOREIGN)
    if _bad:
        return ReconcileRow(ROW_HEALTH, invalid_items=_dedupe(_bad))
    _jq = _to_float_or_none(_in["jq"])
    _fnet = _to_float_or_none(_in["fnet"])
    _r = reconcile_health_score(_jq, score_pct_from(_in["score"], _in["max_score"]), _fnet)
    return ReconcileRow(ROW_HEALTH, result=_r)


def compute_reconcile(session: Mapping[str, Any]) -> ReconcileReport:
    """三列對帳（順序同舊面板：US10Y → 月營收 YoY → 健康評分）。例外一律往上拋（呼叫端轉紅卡）。"""
    return ReconcileReport(rows=(_us10y_row(session), _rev_yoy_row(session),
                                 _health_row(session)))
