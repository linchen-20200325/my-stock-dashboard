"""src/compute/macro/warroom_summary.py — `warroom_summary` 13 欄的**純組裝**（L2，批 Z60）。

═══ 為什麼有這個檔（切換前必做 RA-1）═══════════════════════════════════
新 UI 讀總經位階／建議持股全部經 `warroom_summary`（`get_macro_state()`、
`allocation_service.get_allocation()`、五桶 health 燈、旌旗退路…），而它在全 repo
**只有舊 UI 兩處寫入**：

  · TL ＝ `src/ui/tabs/macro/section_traffic_light.py::render_traffic_light_top`
    —— **整包賦值** 13 欄（含 `throttle`）；
  · SS ＝ `src/ui/tabs/macro/section_state.py::render_section_state`
    —— **就地 update** 12 欄（不含 `throttle`，保留 TL 寫的那一份）。

舊頁正常 rerun 的順序是 TL 先、SS 後，使用者最後看到的是「**SS 的 12 欄 ＋ TL 的
throttle**」。本函式把**那個最終結果**組出來，給新 UI 的平行路徑
（`src/services/warroom_apply.py`）用。

═══ 總管拍板方案（a）：平行組裝，舊檔零改動，計算零複製 ═══════════════════
  · **零計算**：燈號／健康分／仲裁全部來自 L2 `calc_traffic_light` 的回傳；
    throttle 來自 L0 `shared.position_throttle.compute_position_throttle`。
    本檔**不含任何門檻數字**，只做「取哪一欄放哪一格」。
  · **舊檔零改動**：TL／SS 兩段原文一字未動，等價性由
    `tests/test_batch_z60.py` 以兩種方式釘住 —— (1) 真的依序跑 TL 與 SS 的
    端到端 golden；(2) 用字面錨把兩段寫入區塊切出來 exec 的格點比對。

═══ 為什麼能用「一次組裝」表達兩個寫入端 ════════════════════════════════
兩端吃的是**同一份** `load_section_inputs(session)` 的 mkt / jingqi / cl_data / li。
唯一可能不同的是 jingqi 的 warroom 退路（SS 跑的時候 session 裡已是 TL 剛寫的
warroom）：TL 寫入的 `jingqi_avg` ＝ `_safe_float(上一份的 jingqi_avg)`，SS 再讀回
同一個值；`jingqi_info=None` 與 `{'avg': None}` 在 `calc_traffic_light` 內除了
「三來源全空」那道早退之外處處等價，而那道早退成立時 TL 根本不寫、SS 也拿不到
warroom 可退。⇒ 同一輪裡 TL 的 `tl` 與 SS 的 `tl` 相同，最終結果可由**同一個 tl**
組出。這一段推導本身也被端到端 golden 實跑檢驗（含自我回授情境）。

逐欄出處（最終值以 SS 為準，throttle 以 TL 為準）::

    traffic_light     ← tl['label']
    health_score      ← tl['health']
    regime            ← mkt_info.get('regime')        # SS 寫法：缺值 None，⛔ 不捏 'neutral'
    effective_regime  ← tl['effective_regime']
    light             ← tl['light']
    regime_source     ← tl['regime_source']
    market_score      ← tl['score']
    jingqi_avg        ← tl['jqavg']
    leek_index        ← tl['leek']
    foreign_net_bn    ← tl['fnet']
    futures_net       ← tl['fut_net']
    confidence_pct    ← tl['conf']
    throttle          ← TL 規則：health 有值才算，否則 None（⛔ 不補 0）

⚠️ TL 自己寫 `regime` 時用的是 `mkt_info.get('regime', 'neutral')`，但那個值**每一輪
都被 SS 蓋回 `.get('regime')`**（SS 跑得到的條件與 TL 寫入的條件相同）——
使用者從來看不到 TL 那一版，所以本檔取 SS 的。

⚠️ 不含時間戳：13 欄契約本來就沒有時間欄位（`get_macro_state()` 也不讀），
本批不改契約。

分層（CLAUDE.md §8.2）：L2 純函式 —— 零 I/O、不 import streamlit、只依賴 L0。
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from shared.position_throttle import compute_position_throttle

#: 舊頁 TL→SS 跑完之後 `warroom_summary` 的**全部**鍵（順序＝TL 整包賦值時的順序，
#: SS 的就地 update 不改順序）。逐一對過兩個寫入端的原文（2026-10-14）。
WARROOM_SUMMARY_KEYS: tuple[str, ...] = (
    "traffic_light",
    "health_score",
    "regime",
    "effective_regime",
    "light",
    "regime_source",
    "market_score",
    "jingqi_avg",
    "leek_index",
    "foreign_net_bn",
    "futures_net",
    "confidence_pct",
    "throttle",
)


def build_warroom_summary(tl: Optional[Mapping[str, Any]],
                          mkt_info: Optional[Mapping[str, Any]]) -> Optional[dict]:
    """由 `calc_traffic_light` 的回傳組出舊頁 TL→SS 之後的那份 `warroom_summary`。

    Args:
        tl: `calc_traffic_light(...)` 的回傳；`None`（三來源全空）時回 `None`。
            ⚠️ 取欄一律用 `[...]`：兩個寫入端裡至少有一端是 `[...]` 取值，
            契約缺欄時舊頁會拋 KeyError —— 本函式同樣拋，⛔ 不悄悄填 None。
        mkt_info: 與 `tl` 同一輪的 `mkt_info`（`load_section_inputs(...).mkt_info`）。
            只取 `regime`（趨勢面**輸入**，僅供揭露），缺值 None。

    Returns:
        13 鍵 dict（鍵序 ＝ `WARROOM_SUMMARY_KEYS`）；`tl` 為假值時 `None`
        （對齊兩個寫入端的 `if _tl_init:` / `if _tl_final:` —— 不寫）。
    """
    if not tl:
        return None
    _mkt = mkt_info or {}
    # TL：`_tl_eff_reg = (_tl_init or {}).get('effective_regime') or None`
    _eff_for_throttle = tl.get("effective_regime") or None
    # TL（批 Z8）：health 缺就不算，throttle 寫 None（⛔ 不補 0 —— 0 分是「防禦」）。
    _throttle = None
    if tl["health"] is not None:
        _throttle = compute_position_throttle(
            float(tl["health"]), regime=_eff_for_throttle,
            defense=bool(tl.get("defense")))
    return {
        "traffic_light": tl["label"],
        "health_score": tl["health"],
        "regime": _mkt.get("regime"),
        "effective_regime": tl["effective_regime"],
        "light": tl["light"],
        "regime_source": tl["regime_source"],
        "market_score": tl["score"],
        "jingqi_avg": tl["jqavg"],
        "leek_index": tl["leek"],
        "foreign_net_bn": tl["fnet"],
        "futures_net": tl["fut_net"],
        "confidence_pct": tl["conf"],
        "throttle": _throttle,
    }
