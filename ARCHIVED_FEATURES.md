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

**模組保留磁碟**:
- `tab_macro_validation.py`(已刪原始 file,但 import path 預留 — user 復活時需重建)
- `src/compute/macro/macro_validation_tw.py`(留)
- `src/compute/macro/macro_signal_lookback_tw.py`(留)
- `src/compute/scoring/multi_factor_optimization.py`(留)

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
