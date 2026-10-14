"""src/services/warroom_apply.py — 新 UI 平行路徑的 `warroom_summary` 寫入端（L3，批 Z60）。

═══ 為什麼有這個檔（切換前必做 RA-1）═══════════════════════════════════
新 UI（`src/ui/views/**`）讀總經位階 / 建議持股全部經 `warroom_summary`，
但頁1「🚀 更新今日戰情」（`macro_refresh_service.refresh_macro_now`）修前**不寫它**——
全 repo 只有舊 UI 兩處寫入（`section_traffic_light.py` 整包賦值、`section_state.py`
就地 update），於是只用新 UI 的人，卡①建議持股 / 卡③市場位階 / health 燈
永遠停在「上一次跑舊分頁」的值，或根本沒有值。

═══ 做法：平行組裝，舊檔零改動，計算零複製（總管拍板方案 a）═══════════════
    load_section_inputs(session)          ← L3（與 TL / SS 同一支）
      → calc_traffic_light(...)           ← L2（引數與 TL / SS 呼叫方式逐字相同）
      → build_warroom_summary(tl, mkt)    ← L2 純組裝（`src/compute/macro/warroom_summary.py`）
      → st.session_state['warroom_summary'] = 新 dict

等價性（舊頁 TL 先、SS 後的**最終結果**）由 `tests/test_batch_z60.py` 的端到端
golden 與格點比對釘住。

═══ 與舊頁刻意不同的地方（逐項講清楚，⛔ 不宣稱零行為變更）═══════════════════
  1. **指定一個新 dict，不就地 update。** `macro_refresh_service._writes_recorded`
     以 `id()` 量測「這一步寫了哪些 key」—— 就地 update 量不到，報告會少講一項。
     內容與舊頁 TL→SS 的最終結果相同（鍵、值、鍵序）。
  2. **整理不出結論就 pop。** `calc_traffic_light` 回 `None`（三來源全空）或這一步
     拋例外時，**刪掉**既有的 `warroom_summary` 並回報原因 —— ⛔ 不讓上一輪的結論
     冒充今天的。對齊舊頁按「🚀 一鍵更新全部數據」時 `_macro_session_reset()`
     **先 pop** 的行為；舊頁在**非更新的 rerun** 中遇到例外時則是留著舊值（整頁被
     `_render_tab_isolated` 換成紅框），兩者不同，此處取前者。
     ⚠️ 例外**不吞**：pop 之後原樣往上拋，由呼叫端記成失敗的步驟（§1）。
  3. **刻意不寫 session `macro_state`。** 舊 TL 另寫 `st.session_state['macro_state']`
     ＝ `get_macro_state(TL 那一版 warroom)`，但那個 key 只有舊頁自己讀；新 UI 一律
     現場呼叫 `get_macro_state()`。多寫一個沒人讀的 key ＝ 多一份會漂的狀態。
  4. **不產生舊 `section_mid.py` 的「三環火力分級偏多，但已被總經／VIX 硬否決壓制」
     那一句被壓制訊號**（`register_conflict`）—— 那是舊頁渲染中期桶時登記的
     **說明文字**，不影響任何數字；本路徑不渲染中期桶。
  5. **沒有時間戳**：13 欄契約本來就沒有時間欄位，本批不改契約。
  6. **`mkt_info` 沒有 `regime` 鍵時寫 `None`，不寫 `'neutral'`。** 舊 TL 用
     `mkt_info.get('regime', 'neutral')` 捏一個「中性」，緊接著 SS 用 `.get('regime')`
     蓋回 `None` —— 所以舊頁 **TL→SS 的最終結果**與本檔相同（golden 情境
     `X_mkt_no_regime` 釘住）；但舊頁**只跑到 TL、SS 沒跑**的那一輪，session 裡留的是
     `'neutral'`。本檔一律照 SS 寫 `None`：缺值就是缺值，⛔ 不以缺值推導「中性」（§1）——
     新路徑較誠實，這是刻意的差異。

⚠️ **自我回授照舊頁，但「三來源全空」以本輪真的輸入判定**：
`load_section_inputs` 在 session 沒有 `jingqi_info` 時會退回**上一份** warroom 的
`jingqi_avg`，合成 `{'avg': ...}`。舊頁每一次 rerun 都是這樣（TL 讀上一份），本檔照做 ——
**只要本輪還有 `mkt_info` 或 `cl_data`**，結果與舊頁 TL→SS 完全相同（golden 釘住）。
唯一的例外是 session 裡 `mkt_info` / `jingqi_info` / `cl_data` **三個都是假值**時：
舊頁 rerun 會拿**上一份 warroom 的 `jingqi_avg`**（＝上一輪的結論）算出一份新的 warroom，
那正是「上一輪的結論冒充今天的」；舊頁按「🚀 一鍵更新全部數據」時則因為先 pop 了
warroom 而得到「沒有 warroom」。本檔取後者 —— 判「三來源全空」看的是 session 的**原始**
三個 key（與 `calc_traffic_light` 開頭那道早退同一個判準），不看退路合成出來的 dict。

分層（CLAUDE.md §8.2）：L3 —— 依賴 L2（`calc_traffic_light` / `build_warroom_summary`）
與 L3（`section_inputs`），零 L4 / L5 import，寫 `st.session_state`。
"""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from src.compute.macro.macro_helpers import calc_traffic_light
from src.compute.macro.warroom_summary import build_warroom_summary
from src.services.section_inputs import load_section_inputs


@dataclass(frozen=True)
class WarroomApplyResult:
    """這一步的結論（呼叫端照這份記報告，不自己判斷）。

    Attributes:
        written: 這一輪有沒有寫出一份新的 `warroom_summary`。
        popped: 這一輪有沒有把**既有**的 `warroom_summary` 刪掉
            （整理不出結論時；session 本來就沒有就是 False）。
        reason: 沒寫的原因（`written=True` 時為空字串）。
        health_missing: 寫了，但健康分兩條腿都缺（`health_score is None`）——
            `get_macro_state()` 會把這份 warroom 視同**未載入**，
            呼叫端要講出來，不能讓「寫了」被讀成「建議持股有了」。
    """

    written: bool
    popped: bool = False
    reason: str = ""
    health_missing: bool = False


#: `calc_traffic_light` 回 None 時的原因（三來源全空）。
REASON_NO_INPUT: str = (
    "大盤評估（mkt_info）、旌旗（jingqi_info）、籌碼（cl_data）三個輸入這一輪都是空的 —— "
    "紅綠燈整理不出結論")


def compute_and_store_warroom_summary() -> WarroomApplyResult:
    """算一次紅綠燈並把舊頁 TL→SS 之後的那份 `warroom_summary` 寫進 session。

    Returns:
        `WarroomApplyResult`。

    Raises:
        任何取輸入 / 判燈 / 組裝時的例外 —— **先** pop 掉既有的 `warroom_summary`，
        再原樣往上拋（⛔ 不吞）。
    """
    try:
        _inp = load_section_inputs(st.session_state)
        # 三來源全空：看**原始** session（見檔頭「自我回授」段）—— 退路合成的
        # `{'avg': 上一份 warroom 的 jingqi_avg}` 是上一輪的結論，不是本輪的來源。
        _no_input = (not _inp.mkt_info and not st.session_state.get('jingqi_info')
                     and not _inp.cl_data)
        if _no_input:
            _wr = None
        else:
            _mkt = _inp.mkt_info or {}
            _tl = calc_traffic_light(
                _mkt,
                _inp.jingqi_info or {},
                _inp.cl_data or {},
                _inp.li_latest,
            )
            _wr = build_warroom_summary(_tl, _mkt)
    except Exception as _e:  # noqa: BLE001 — 不吞：pop 之後原樣往上拋
        _had = "warroom_summary" in st.session_state
        st.session_state.pop("warroom_summary", None)
        print(f"[warroom_apply] ❌ 整理紅綠燈結論失敗：{type(_e).__name__}: {_e} —— "
              f"{'已刪除上一份 warroom_summary' if _had else 'session 本來就沒有 warroom_summary'}"
              "（不讓上一輪的結論冒充今天的）")
        raise
    if _wr is None:
        _had = "warroom_summary" in st.session_state
        st.session_state.pop("warroom_summary", None)
        print(f"[warroom_apply] ⚠️ {REASON_NO_INPUT}"
              f"{' → 已刪除上一份 warroom_summary' if _had else ''}")
        return WarroomApplyResult(written=False, popped=_had, reason=REASON_NO_INPUT)
    # ⚠️ 必須是**新物件**的整個 key 賦值（`_writes_recorded` 以 id 量測寫入）。
    st.session_state['warroom_summary'] = _wr
    return WarroomApplyResult(written=True,
                              health_missing=_wr["health_score"] is None)
