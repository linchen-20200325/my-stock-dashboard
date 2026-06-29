"""src/ui/tabs/macro/ — tab_macro 子模組分區 + INDEX(P1 v18.389)。

═══════════════════════════════════════════════════════════════════════════
📍 段落 → 子模組對照表(AI 直接定位用)
═══════════════════════════════════════════════════════════════════════════

| 段落          | 子模組                  | 函式                       | LOC |
|---------------|------------------------|---------------------------|-----|
| 🚦 紅綠燈卡 + warroom_summary | section_traffic_light.py | render_traffic_light_top | 110 |
| 頂部 📊 總經總結儀表板 + 五桶 bar | section_summary_bar.py | render_five_bucket_summary | 60 |
| 戰情概覽(2-col KPI)    | section_overview.py    | render_section_overview   | 56 |
| 今日作戰室(5min 清單)  | section_warroom.py     | render_section_warroom    | 188 |
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
🚧 殘餘 tab_macro.py(1012 LOC)未抽出的內容
═══════════════════════════════════════════════════════════════════════════

【已下沉至 src/data/macro/macro_snapshot.py(L1 Data)】
- ✅ P3-D1 v18.389:_job_macro 5 sub-fetcher(VIX/CPI/Fed/PMI/NDC/Export)
                   共 604 LOC → fetch_*_block(),_job_macro 縮為 65 LOC orchestrator
- ✅ P3-D2 v18.389:_job_m1b 89 LOC → fetch_m1b_m2_block(3-Tier:CBC/FRED/IMF)
- ✅ P3-D3 v18.389:_job_bias 43 LOC → compute_twii_bias(L2 純函式)

【已下沉至 src/services/(L3 Service)】
- ✅ P3-D4 v18.389:7-job orchestrator(intl/tw/tech/inst/margin/adl/li)+
                   ThreadPoolExecutor + FinMind inst rescue 共 230 LOC →
                   macro_fetch_orchestrator.fetch_macro_bundle()
- ✅ P3-D8 v18.390:Registry patch 161 LOC → macro_registry_patch.patch_registry()
                   (caller 注入 INTL/TW/TECH MAP + rp_entry/scalar/ts 避循環)

【已下沉至 src/ui/tabs/macro/ Dashboard 三件套(v18.390 D-5/D-6/D-7)】
- ✅ P3-D5:五桶 bar 43 LOC → section_summary_bar.render_five_bucket_summary
- ✅ P3-D6:戰情概覽 35 LOC → section_overview.render_section_overview
- ✅ P3-D7:今日作戰室 154 LOC → section_warroom.render_section_warroom

【已下沉至 macro/(P3-D9 v18.391 認錯補做)】
- ✅ 紅綠燈卡 + warroom_summary 寫入 66 LOC → section_traffic_light.py
  (先前以「placeholder 反模式」擋,但 B-S2 已 cross-def 傳 placeholder,
  自我矛盾;補做後 caller 接 3-tuple `(placeholder, show_market_data, tl_eff_reg)`)

【仍留 tab_macro.py(1012 LOC)】
- 長短期雙視角 / 全球風險雷達資料準備(_lt, _slow_v,~64 LOC,LOW 可抽)
- 旌旗指數計算 + write(~32 LOC,LOW 可抽)
- Outer trio executor + macro/m1b/bias session_state writes(~80 LOC,MEDIUM)
- 市場評估 calc + mkt_info write(~80 LOC,MEDIUM)
- Late imports + 函式入口 + button + early gate(~73 LOC,真不可抽)
- render_section_* call + intl/tw/tech/inst/margin bridge(~100 LOC,orchestrator)

剩餘真不可抽 ~180 LOC(orchestrator + Streamlit button + early gate)。
剩餘可抽 ~280 LOC(D-10~D-13,屬下一場戰役;ROI 拐點接近)。

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
