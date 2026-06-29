# ARCHIVED_FEATURES — 已封存功能與復活步驟(v18.395 P5-A4 新檔)

> 從 tab_macro.py / 其他主程式碼搬出的 archived 說明,讓主程式碼乾淨。
> 封存 ≠ 刪除:模組保留磁碟,user 主動要求即可復活。

---

## §十:📊 總經訊號歷史驗證(v18.191 archived)

**封存原因**:user 反饋總經面板過於複雜(v18.190 已砍雙視角 + AI 總裁決),
進一步封存歷史驗證區(C 區)。

**5 個 expander 內容**:
1. 🎯 TWII Crisis 事件清單 + Phase 1 events
2. 🚦 Phase 3 訊號預測力驗證(命中率總覽 + 逐事件明細 + 📐 精確率分析)
3. 📡 跨資料源比對視角矩陣(Phase E)
4. 🎯 MT5-style 自動校準(walk-forward + 3 重 anti-overfit gate)
5. 🔬 多因子權重最佳化(高原區 + walk-forward OOS)

**「半 archive」架構說明**(v18.395 P5-Batch2 deep-dive 確認的設計):

| Layer | 狀態 |
|---|---|
| L6 App `app.py` 不掛 tab_macro_validation | ✅ archived(無 import,UI 不渲染) |
| L5 UI `src/ui/tabs/tab_macro_validation.py` | 🟡 留磁碟(688 LOC,user 復活時直接 import) |
| L4 Render(無) | — |
| L3 Service(無) | — |
| L2 Compute `src/compute/macro/macro_validation_tw.py` | ✅ live(crisis event detection 邏輯) |
| L2 Compute `src/compute/macro/macro_signal_lookback_tw.py` | ✅ live(8 fetch_*_series + provenance) |
| L2 Compute `src/compute/scoring/multi_factor_optimization.py` | ✅ live(weight optimization engine) |
| L0 SSOT `shared/signal_thresholds.py` | ✅ macro_signal_lookback_tw 用的 4 訊號閾值 |
| Tests | ✅ 3 test file 還在跑(`test_macro_signal_lookback_tw.py` /<br>`test_multi_factor_optimization.py` / `test_pr_q5a_msl_nas_provenance.py`) |

**這是刻意的設計**:UI 砍掉但後端保留 — user 復活只需在 `app.py` 重 hook,不需重建 compute/scoring 引擎。
測試還在跑 = 驗證後端邏輯仍 work。

**禁止真刪**(2026-06-29 P5-Batch2 audit 確認):
- 真刪會破壞 S-PROV-1 守衛測試
- 真刪會 break compute/__init__.py + scoring/__init__.py re-export(可能影響其他 import path)
- 留磁碟成本低(~1500 LOC compute 邏輯 + 3 test file)

**復活步驟**(1 分鐘工):
在 `src/ui/tabs/tab_macro.py` 的 `# F-7.1 B-3:§十一 News AI 總裁決` 之前,加 5 行:
```python
try:
    from tab_macro_validation import render_history_validation_section
    render_history_validation_section()
except Exception as _e_hv:
    st.caption(f"⚠️ 歷史驗證 section 載入失敗:{_e_hv}")
```

(若 `tab_macro_validation.py` 已刪,需先重建或從 git history 撈回)

---

## §九(v18.190 archived 雙視角 + AI 總裁決)

(備註位置:同期 archived,UI 已刪;`section_long_term.py:_lt` 部分復用為「雷達 slow_verdict 派生資料源」。)
