"""section_inputs.py — Stock tab_macro 共享資料層(L3 service,C1-A v18.287)

CLAUDE.md §8.1 step 1:**單一職責** = 從 streamlit session_state 集中讀取
tab_macro 各 section / 5 桶所需的 input bundle,讓各 section 不必各自重複
9~12 個 session_state.get(...) 呼叫,降低物理重排時的耦合度。

C1 series 計畫
-------------
- ✅ C1-A v18.287(本檔):建立 SectionInputs dataclass + load_section_inputs()
  helper,先接入 5 桶 summary 一個 caller 驗證 pattern
- ⏳ C1-B+:逐步把其餘 6 個 section(戰情概覽 / 今日作戰室 / etc.)接入,
  最後再重排物理順序(C1 系列終點)

設計權衡(§8.1 step 6 自評過度設計)
---------------------------------
為什麼用 dataclass 而非 plain dict?
- frozen=True 防 caller 誤改 → §1 Fail Loud 對齊(輸入污染立擋)
- 名稱明確型別(Optional[dict] 等)→ IDE 補全 + caller 不需記憶 key 拼字
- 但**不引入** Pydantic / pandera schema(過度設計):本層只是 session_state
  reads bundling,無外部 I/O / 無契約驗證需求

依賴方向(§8.2)
--------------
- L3 service → 純函式,無 streamlit / requests / yfinance / FinMind 依賴
- 接 dict 參數(由 caller 傳 session_state),**不**直接 import streamlit
  (caller 在 L5 tab_macro 已是 streamlit context;本檔保純函式以便 unit test)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class SectionInputs:
    """tab_macro 各 section / 5 桶共用的 input bundle。

    所有欄位都是 Optional — 對應 session_state 在「首次載入」/「快取過期」/
    「上游全敗」三態都可能缺。各 section consumer 須自行決定缺值時:
    (a) 灰燈擱置(§1 Fail Loud),或 (b) 用 gating 不渲染。
    """
    macro_info: Optional[dict] = None
    mkt_info: Optional[dict] = None
    warroom_summary: Optional[dict] = None
    m1b_m2_info: Optional[dict] = None
    bias_info: Optional[dict] = None
    cl_data: Optional[dict] = None
    li_latest: Any = None
    jingqi_info: Optional[dict] = None
    news_items: Optional[list] = None


def load_section_inputs(state: dict) -> SectionInputs:
    """從 streamlit session_state(或等價 dict)讀取各 section 共用 inputs。

    Parameters
    ----------
    state : dict
        streamlit `st.session_state`(或測試用 plain dict)。

    Returns
    -------
    SectionInputs
        frozen dataclass;欄位語意對齊 macro_helpers.compute_five_bucket_summary
        各 kwarg。

    Notes
    -----
    - jingqi_info 改為從 warroom_summary['jingqi_avg'] 衍生(現況 tab_macro 寫法,
      非 session_state['jingqi_info'] 直讀);保持與 caller 等價。
    - news_items 從 session_state['_macro_news_items'](雙底線 prefix,內部 key)。
    - 任何 .get 缺值都回 None,**不**填預設值(對齊 §1 Fail Loud)。
    """
    if state is None:
        return SectionInputs()
    wr5 = state.get('warroom_summary') or {}
    return SectionInputs(
        macro_info=state.get('macro_info'),
        mkt_info=state.get('mkt_info'),
        warroom_summary=wr5,
        m1b_m2_info=state.get('m1b_m2_info'),
        bias_info=state.get('bias_info'),
        cl_data=state.get('cl_data'),
        li_latest=state.get('li_latest'),
        jingqi_info={'avg': wr5.get('jingqi_avg')} if wr5 else None,
        news_items=state.get('_macro_news_items'),
    )
