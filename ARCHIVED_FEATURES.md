# ARCHIVED_FEATURES — 已封存功能與復活步驟(v18.395 P5-A4 新檔)

> 從 tab_macro.py / 其他主程式碼搬出的 archived 說明,讓主程式碼乾淨。
> ~~封存 ≠ 刪除:**backend compute 模組保留磁碟,user 主動要求即可復活;UI wrapper 已真刪,需從 git history 撈回。**~~
>
> ⚠️ **2026-08-28 實測已不成立,就地更正(原句加刪除線保留,不刪)**:
> 「backend compute 模組**保留磁碟**」這句在寫下的當天是**對的** —— v18.399 R6 只真刪了
> UI wrapper,三個 backend compute 模組當時確實還在磁碟上,「user 主動要求即可復活」
> 因此是可兌現的承諾。**它是被後來的一次改動推翻的,不是當初寫錯**:
> commit `9f61437`(PR #623,2026-08-19,「移除 Bucket A 封閉死碼簇(5 模組 ~1,760 LOC)」)
> 把整個封閉死碼簇連同其測試一起移除,本檔卻沒有跟著更新。
> **現況:backend 與 UI 都只在 git history 裡**,復活成本從「撈一個 UI 檔」變成
> 「撈一整簇 backend + UI」。逐檔實測結果見下方 §十 表格的更正列。

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
| L2 Compute `src/compute/macro/macro_validation_tw.py` | ~~✅ live(crisis event detection 邏輯,157 LOC)~~ → ❌ **已刪**(`9f61437` / PR #623,2026-08-19;刪除當下實測 134 行,原文寫的 157 行不符) |
| L2 Compute `src/compute/macro/macro_signal_lookback_tw.py` | ~~✅ live(8 fetch_*_series + S-PROV-1 provenance,588 LOC)~~ → ❌ **已刪**(同 `9f61437`;刪除當下實測 581 行,原文寫的 588 行不符) |
| L2 Compute `src/compute/scoring/multi_factor_optimization.py` | ~~✅ live(weight optimization engine,527 LOC)~~ → ❌ **已刪**(同 `9f61437`;刪除當下實測 521 行,原文寫的 527 行不符) |
| L0 SSOT `shared/signal_thresholds.py` | ✅ **未隨 `9f61437` 一起移除**(這是歷史事實,不會過期;至於「現在還在不在」請自行 `ls`,2026-08-28 實測為在)。原因:它**不專屬本功能**,另有大量其他 consumer,故不在 PR #623 的刪除範圍內。<br>⚠️ **本列只宣稱上面這一件事,不宣稱「全表只有這一列是對的」** —— 同表的 `app.py` 未掛載、L5 UI 已真刪兩列,2026-08-28 一併實測**亦與現況相符**(`grep -c tab_macro_validation app.py` → 0;`ls src/ui/tabs/tab_macro_validation.py` → No such file) |
| Tests | ~~✅ 12 backend test 全保留(`test_macro_signal_lookback_tw.py` 30 case /<br>`test_multi_factor_optimization.py` 28 case /<br>`test_macro_validation_tw.py` 9 case)~~ → ❌ **三個測試檔全數已刪**(同 `9f61437`)。<br>另:原文的 case 數也不準,刪除當下實測為 37 / 32 / 9(共 78,非 12)。「7 個 source-string 守衛 test 同步退役」該句未查證,維持原狀不背書 |

> ⚠️ **2026-08-28 逐檔實測更正(原表格內容加刪除線保留,不刪乾淨)**。
> **為什麼不整段刪掉**:刪乾淨會讓後人以為這裡沒出過事。這張表曾經是對的 ——
> 它寫於 v18.399 R6,當時三個 backend 模組與三個測試檔**確實都在磁碟上**,
> 「封存 ≠ 刪除」的承諾當時可以兌現。真正發生的是 **PR #623 在 2026-08-19 把它們
> 當成「封閉死碼簇」整批移除**,而本檔沒有跟著更新,於是一份原本正確的文件
> 在九天之內變成一份會誤導人的文件。留著刪除線,是為了讓下一個人看得到
> 「文件與程式碼各自演化、沒有人負責同步」這個**失效模式本身**。
> **對照 CLAUDE.md §-2**:「沒查證的宣稱比沒有宣稱更危險」—— 一份自稱 `✅ live`
> 的清單,會讓下一個做清理的人(含未來的 AI)建立在假前提上繼續蓋。
>
> **查證方法(可重跑)**:
> ```
> ls src/compute/macro/macro_validation_tw.py            # → No such file
> git log --oneline --diff-filter=D -1 -- <各檔>          # → 9f61437
> git show 9f61437^:<各檔> | wc -l                        # → 刪除當下的真實行數
> ```

**復活步驟**(若 user 將來要復活 UI):

> ⚠️ **2026-08-28 更正:下列 4 步已不足以復活。** 它們寫於「backend 還在磁碟上」的年代,
> 只處理 UI 那一層。PR #623 把 backend 三模組一起刪掉之後,**照這 4 步做會得到一個
> import 不到 backend 的壞 UI**。現在要復活,必須**先**從 `9f61437^` 撈回
> `macro_validation_tw.py` / `macro_signal_lookback_tw.py` / `multi_factor_optimization.py`
> (以及要不要一併撈回三個測試檔),**再**做下列 4 步。
> ⚠️ 且復活 UI = 分頁動線異動,依 CLAUDE.md §-1.5 v3 `03`-2 ① **須先出線框草稿送客戶拍板**。

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
