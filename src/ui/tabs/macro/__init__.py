"""src/ui/tabs/macro/ — tab_macro 子模組分區 + INDEX(P1 v18.389)。

═══════════════════════════════════════════════════════════════════════════
📍 段落 → 子模組對照表(AI 直接定位用)
═══════════════════════════════════════════════════════════════════════════

| 段落          | 子模組                  | 函式                       | LOC |
|---------------|------------------------|---------------------------|-----|
| §一 拐點 / §六 現金流向 / §七 長期桶 | section_long.py        | render_section_long       | 426 |
| §二 拐點偵測 / 市場狀態 | section_state.py       | render_section_state      | 402 |
| §三 籌碼桶(法人/融資/先行指標) | section_chips.py       | render_section_chips      | 592 |
| §五 短線急殺桶          | section_short.py       | render_section_short      | 342 |
| §八 總經拼圖 v4.0       | section_mid.py         | render_section_mid        | 458 |
| §九 跨桶 AI 投資決策    | section_cross_ai.py    | render_section_cross_ai   | 246 |
| §十一 News AI 總裁決    | section_news_ai.py     | render_section_news_ai    | 323 |
| 共用 inner def(refresh handler) | handlers.py            | _macro_session_reset / _on_refresh_click / _on_force_clear_click / _render_traffic_light | 153 |
| 純函式 helper(8 個 KPI / 雷達 / banner) | helpers.py             | _radar_threshold_lines / _render_macro_indicator_card / _render_global_risk_bucket / render_five_bucket_bar / 等 | 462 |

═══════════════════════════════════════════════════════════════════════════
🧭 reading order(tab_macro.py 中 render_section_* 呼叫順序)
═══════════════════════════════════════════════════════════════════════════

紅綠燈卡 → 五桶 bar → 戰情概覽 → 今日作戰室
  → render_section_state  (§二 拐點偵測)
  → render_section_long   (§一/§六/§七 長期桶群)
  → render_section_mid    (§八 總經拼圖)
  → render_section_short  (§五 短線急殺)
  → 🌍 全球風險桶(_render_global_risk_bucket,在 helpers.py)
  → render_section_chips  (§三 籌碼)
  → render_section_cross_ai (§九 跨桶 AI)
  → 歷史驗證(§十 archived)
  → render_section_news_ai  (§十一 News AI)

═══════════════════════════════════════════════════════════════════════════
🚧 殘餘 tab_macro.py(1445 LOC)未抽出的內容(屬 §8.2 分層治理)
═══════════════════════════════════════════════════════════════════════════

【已下沉至 src/data/macro/macro_snapshot.py(L1 Data)】
- ✅ P3-D1 v18.389:_job_macro 5 sub-fetcher(VIX/CPI/Fed/PMI/NDC/Export)
                   共 604 LOC → fetch_*_block(),_job_macro 縮為 65 LOC orchestrator
- ✅ P3-D2 v18.389:_job_m1b 89 LOC → fetch_m1b_m2_block(3-Tier:CBC/FRED/IMF)
- ✅ P3-D3 v18.389:_job_bias 43 LOC → compute_twii_bias(L2 純函式)

【已下沉至 src/services/macro_fetch_orchestrator.py(L3 Service)】
- ✅ P3-D4 v18.389:7-job orchestrator(intl/tw/tech/inst/margin/adl/li)+
                   ThreadPoolExecutor + FinMind inst rescue 共 230 LOC →
                   fetch_macro_bundle(),caller 留 st.spinner + session_state writes

【仍留 tab_macro.py(行號隨修改變動,以 grep 為準)】
- L162-232 紅綠燈卡(_tl_placeholder lifecycle,跨 5 處 ref)
- L303-341 五桶 bar 渲染
- L371-558 戰情概覽 + 今日作戰室
- Registry patch(個股/ETF data_registry session 更新,~165 LOC)
- session_state writes 收尾(cl_data / cl_ts / li_latest / _last_inst 等)

剩餘真不可抽:紅綠燈 placeholder lifecycle(streamlit st.empty 跨 def 反模式)。
剩餘可動:Registry patch 可抽 service,但 ROI 低、user 沒指派 → §-1。

═══════════════════════════════════════════════════════════════════════════
📐 PEP 562 lazy forward(caller 可用 `from src.ui.tabs.macro import X` 取)
═══════════════════════════════════════════════════════════════════════════
"""
from . import helpers  # noqa: F401

_SUBMODULES = (helpers,)


def __getattr__(name):
    for sub in _SUBMODULES:
        if name in vars(sub):
            return getattr(sub, name)
    raise AttributeError(f"module 'src.ui.tabs.macro' has no attribute {name!r}")
