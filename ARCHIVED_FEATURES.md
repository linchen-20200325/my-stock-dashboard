# ARCHIVED_FEATURES — 已封存功能與復活步驟(v18.395 P5-A4 新檔)

> 從 tab_macro.py / 其他主程式碼搬出的 archived 說明,讓主程式碼乾淨。
> 封存 ≠ 刪除:**backend compute 模組保留磁碟,user 主動要求即可復活;UI wrapper 已真刪,需從 git history 撈回。**

---

## §十:📊 總經訊號歷史驗證(v18.191 UI archived → v18.399 R6 UI 真刪)

**封存原因**:user 反饋總經面板過於複雜(v18.190 已砍雙視角 + AI 總裁決),
進一步封存歷史驗證區(C 區)。

**5 個 expander 內容**:
1. 🎯 TWII Crisis 事件清單 + Phase 1 events
2. 🚦 Phase 3 訊號預測力驗證(命中率總覽 + 逐事件明細 + 📐 精確率分析)
3. 📡 跨資料源比對視角矩陣(Phase E)
4. 🎯 MT5-style 自動校準(walk-forward + 3 重 anti-overfit gate)
5. 🔬 多因子權重最佳化(高原區 + walk-forward OOS)

**v18.399 R6 真刪 audit 翻案**:原 P5-Batch2「禁止真刪」3 理由全證偽:
- ❌ ~~「真刪會破壞 S-PROV-1 守衛測試」~~ — S-PROV-1 全在 backend `macro_signal_lookback_tw.py:40-54`,UI 檔 0 依賴
- ❌ ~~「真刪會 break compute/__init__.py re-export」~~ — `compute/__init__.py` 留空(7 LOC),且 UI 檔在 `src/ui/tabs/` 不在 compute 層
- ⚠️ ~~「留磁碟成本低」~~ — 半真,但跟「禁止刪 UI」無因果

UI 檔 780 LOC 純 Streamlit wrapper,0 unique 邏輯,100% 委派 backend。已真刪。

**現況架構**:

| Layer | 狀態 |
|---|---|
| L6 App `app.py` 不掛 tab_macro_validation | ✅ archived(無 import,UI 不渲染) |
| L5 UI `src/ui/tabs/tab_macro_validation.py` | ❌ **已真刪**(v18.399 R6,git history 可撈) |
| L4 Render(無) | — |
| L3 Service(無) | — |
| L2 Compute `src/compute/macro/macro_validation_tw.py` | ✅ live(crisis event detection 邏輯,157 LOC) |
| L2 Compute `src/compute/macro/macro_signal_lookback_tw.py` | ✅ live(8 fetch_*_series + S-PROV-1 provenance,588 LOC) |
| L2 Compute `src/compute/scoring/multi_factor_optimization.py` | ✅ live(weight optimization engine,527 LOC) |
| L0 SSOT `shared/signal_thresholds.py` | ✅ macro_signal_lookback_tw 用的 4 訊號閾值 |
| Tests | ✅ 12 backend test 全保留(`test_macro_signal_lookback_tw.py` 30 case /<br>`test_multi_factor_optimization.py` 28 case /<br>`test_macro_validation_tw.py` 9 case);7 個 source-string 守衛 test 同步退役 |

**復活步驟**(若 user 將來要復活 UI):
1. `git log --all -- src/ui/tabs/tab_macro_validation.py` 找到刪除前最後一個 commit
2. `git show <sha>:src/ui/tabs/tab_macro_validation.py > src/ui/tabs/tab_macro_validation.py`
3. 在 `src/ui/tabs/tab_macro.py` 的 `# F-7.1 B-3:§十一 News AI 總裁決` 之前,加 5 行:
```python
try:
    from src.ui.tabs.tab_macro_validation import render_history_validation_section
    render_history_validation_section()
except Exception as _e_hv:
    st.caption(f"⚠️ 歷史驗證 section 載入失敗:{_e_hv}")
```
4. 把 `src/ui/tabs/__init__.py` 內 `tab_macro_validation` 加回 `_SUBMODULES` tuple

---

## §九(v18.190 archived 雙視角 + AI 總裁決)

(備註位置:同期 archived,UI 已刪;`section_long_term.py:_lt` 部分復用為「雷達 slow_verdict 派生資料源」。)
