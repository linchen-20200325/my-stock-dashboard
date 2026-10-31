# Phase 4 P4-5｜客戶裁示落盤（DEC-119）＋F1 圖 A 圖例修正＋Gate 重判

- **日期**：2026-10-31｜**分支**：`ccr-c8ef17de-9tw7yt`（`origin/main` 仍為 `228b9fa9`，未前進；PR #987 head）｜**狀態**：本地 commit，**未 push、未開 PR**；單組產出，未經第二組驗證。
- **依據**：`docs/DECISIONS.md` **DEC-119**（客戶原文 fence）。

## 動檔
| 檔 | 內容 |
|---|---|
| `src/ui/views/_market_blocks.py` | 圖 A：`st.line_chart` → `st.vega_lite_chart`（`render_twii_chart`／`twii_chart_spec`／`twii_chart_long`；`twii_chart_frame` 不變）。圖高仍 `PRIMARY_CHART_HEIGHT_PX`＝220；圖例置底 3 欄、短名；「最新值，參考」限定語移到圖例標題；完整系列名逐字留在資料與 tooltip；固定色票 |
| `tests/test_p4_2_market_charts.py` | `TestC41` 圖 A 守衛改為 vega spec 語意守衛（不降強度）；p4_4 `TestA6…` 文字註記更新（仍釘 220） |
| `docs/**`、`PROJECT_RULES.md` | DEC-119、Gate §8、GATE_REPORT §16、HANDOFF／PROJECT_STATE／BACKLOG、PROJECT_RULES 第 24.2 節 📌 |
| `docs/vnext/phase4_market/p4_5/` | 量測腳本（沿用 p4_4／新增 legend）、JSON、截圖、`mutation_p4_5.py` |

## 零資料語意 (a)～(g)
(a) 新資料源 0；(b) schema 0；(c) 公式／門檻／TTL 0（`src/services|compute|data`、`shared/` 0 diff）；(d) Risk Cap 數字顯示 0；(e) 趨勢定義 0（`⬜ 尚未定義` 照舊；MA 仍為最新值水平參考線）；(f) Digest／Brain import 0；(g) `page_today.py`、`app.py`、`requirements.txt`、`compact.py`、`page_market.py` 0 diff ⇒ z60 指紋、page_css sha、P4 還原鏈 pair 不變（`git diff` 可驗）。

## mutation（`python docs/vnext/phase4_market/p4_5/mutation_p4_5.py`；15 項全部轉紅，最後還原）
M1 拿掉 legend／M2 legend 少一項／M3 y 軸 hidden／M4 y 軸刻度標籤關閉／M5 資料 normalize／M6 缺口 ffill／M7 圖高 140／M8 legend 5 欄（右緣超出手機圖寬）／M9 圖例標題丟限定語／M10 色彩對調／M11 sparkline 化（width 120）／M12 圖例標籤帶回限定語／M13 加 window 滾動 transform／M14 tooltip 丟完整系列名／M15 退回 `st.line_chart`。

## 未驗
真資料態、手機實機、Streamlit Cloud、Safari／Firefox、1.57～1.58、淺色主題外觀、CI、獨立 QA 複驗。詳見 `p4_3/GATE_REPORT.md` §16.4。
