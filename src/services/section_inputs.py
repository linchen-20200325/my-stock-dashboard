"""src/services/section_inputs.py — Stock tab_macro 共享資料層(L3 service,C1-A v18.287)

CLAUDE.md §8.1 step 1:**單一職責** = 從 streamlit session_state 集中讀取
tab_macro 各 section / 5 桶所需的 input bundle,讓各 section 不必各自重複
9~12 個 session_state.get(...) 呼叫,降低物理重排時的耦合度。

C1 series 計畫
-------------
- ✅ C1-A v18.287:建立 SectionInputs dataclass + load_section_inputs() helper,
  先接入 5 桶 summary 一個 caller 驗證 pattern
- ✅ C1-B v18.288(本檔):戰情概覽 section 接入;jingqi_info 語意升級為「優先
  讀 session_state['jingqi_info'] 全 dict,fallback 合成 {'avg': warroom['jingqi_avg']}」;
  新增 last_inst 欄位(對應 _ov_inst 雙源 fallback)
- ⏳ C1-C+:逐步把其餘 5 個 section(今日作戰室 / 紅綠燈 / 全球雷達 etc.)接入,
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
    last_inst: Optional[dict] = None       # C1-B:_ov_inst 雙源 fallback 用
    cl_ts: str = ''                         # C1-C:cl_data 的時間戳(_mi_upd / _cl_ts_str / _wr_ts 三 caller 共用)
    futures_net: int = 0                    # C1-C:期貨多空淨額(int,0 為 fail-safe 預設,匹配 evaluate_market_status_v4_final 介面)
    last_inst_date: Any = None              # C1-F:registry 三大法人「last_updated」時間戳的 fallback
    last_margin: Any = None                 # C1-F:cl_data['margin'] fallback(可為數值 / DataFrame 等)


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
    - jingqi_info 解析優先序(C1-B v18.288):
      1. `session_state['jingqi_info']` 真實 dict(由 tab_macro:1221/3781/3927 寫入,
         含 avg/pos/regime/color/label/source/pct20/pct60/pct120/pct240 etc.)
      2. fallback 合成 `{'avg': warroom_summary['jingqi_avg']}`
         (對齊 macro_helpers.calc_traffic_light:71 `_jq.get('avg', 50)` —
          warroom['jingqi_avg'] 即 jingqi_info['avg'],兩者值等價)
      兩 caller(5 桶 + 戰情概覽)downstream 都僅讀 'avg' key,語意統一不破壞行為。
    - last_inst:雙源 fallback,`cl_data['inst']` 為主、`session_state['_last_inst']` 為備
      (對齊 tab_macro:669 `_ov_cd.get('inst') or st.session_state.get('_last_inst', {})`)。
    - news_items 從 session_state['_macro_news_items'](雙底線 prefix,內部 key)。
    - 任何 .get 缺值都回 None,**不**填預設值(對齊 §1 Fail Loud)。
    """
    if state is None:
        return SectionInputs()
    wr5 = state.get('warroom_summary') or {}
    # jingqi_info: 優先讀 session_state 真實 dict,fallback 合成
    _jq_real = state.get('jingqi_info')
    if _jq_real:
        jq = _jq_real
    elif wr5:
        jq = {'avg': wr5.get('jingqi_avg')}
    else:
        jq = None
    return SectionInputs(
        macro_info=state.get('macro_info'),
        mkt_info=state.get('mkt_info'),
        warroom_summary=wr5,
        m1b_m2_info=state.get('m1b_m2_info'),
        bias_info=state.get('bias_info'),
        cl_data=state.get('cl_data'),
        li_latest=state.get('li_latest'),
        jingqi_info=jq,
        news_items=state.get('_macro_news_items'),
        last_inst=state.get('_last_inst'),
        cl_ts=state.get('cl_ts', '') or '',
        futures_net=int(state.get('futures_net', 0) or 0),
        last_inst_date=state.get('_last_inst_date'),
        last_margin=state.get('_last_margin'),
    )
