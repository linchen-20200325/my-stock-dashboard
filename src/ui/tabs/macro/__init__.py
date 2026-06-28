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
🚧 殘餘 tab_macro.py(2260 LOC)未抽出的內容(屬 §8.2 分層治理)
═══════════════════════════════════════════════════════════════════════════

- L162-232 紅綠燈卡(_tl_placeholder lifecycle,跨 5 處 ref)
- L303-341 五桶 bar 渲染
- L371-558 戰情概覽 + 今日作戰室
- L605-840 7 個 _job_*(intl/tw/tech/inst/margin/adl/li)+ ThreadPoolExecutor
- L843-2005 _job_m1b / _job_bias / _job_macro 三巨型 inline def(共 1163 LOC)
- L2006-2168 Registry patch(個股/ETF data_registry session 更新)

這些是 fetch + state 邏輯,目前留在 UI 檔內;真重構需下沉到
src/data/macro/ + src/services/macro_fetch_orchestrator.py(屬另一場戰役)。

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
