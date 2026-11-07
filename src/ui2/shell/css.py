"""New UI2 CSS（`ui2-` 前綴；手機優先、保守）。

- 用 `currentColor`／半透明底色，亮暗主題皆可讀（⛔ 假設白底）。
- 卡片網格 `auto-fit minmax(150px,1fr)`：390px 寬為 2 欄、桌機自動多欄（⛔ 先做桌機再縮）。
- 顏色不是唯一載體：每個 chip 都有文字／符號（Freeze §4.1）。
"""
CSS = """
<style>
.block-container{padding-bottom:2rem !important}
@media (max-width:640px){.block-container{padding-left:.9rem !important;padding-right:.9rem !important}}
/* P1：單行標示（示意資料／Real-data）；note 與標示同一行（窄螢幕才折行） */
.ui2-banner{border:1px dashed currentColor;border-radius:8px;padding:4px 10px;margin:0 0 8px 0;
  background:rgba(128,128,128,.10);font-size:.8rem;line-height:1.4}
.ui2-banner__note{display:inline;opacity:.8;font-size:.72rem;margin-left:.5em}
@media (max-width:640px){.ui2-banner__note--wide{display:none}}   /* 手機：長標示（Real-data）不再附說明，維持單行 */
/* P1：UI2 專用——隱藏 Streamlit 開發者工具列（Deploy／⋮）；只作用於本入口（app_ui2.py）載入的 CSS，不動 .streamlit/config.toml。
   ⚠ Streamlit Cloud 上是否本來就不顯示／是否能被此規則隱藏：未驗（BACKLOG NUI2-PREVIEW-DEV-SURFACE）。 */
[data-testid="stToolbar"],[data-testid="stAppDeployButton"],.stAppDeployButton,[data-testid="stMainMenu"]{display:none !important}
/* P1：開發／測試工具區（僅 ?ui2_dev=1）——虛線框＋等寬字，與產品元件明顯區隔 */
.st-key-ui2_dev_surface{border:2px dashed currentColor;border-radius:8px;padding:8px 12px;margin:24px 0 8px 0;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:rgba(128,128,128,.08)}
.ui2-dev__head{font-weight:700;font-size:.85rem;margin:0 0 4px 0}
.ui2-pagetitle{font-size:1.35rem;font-weight:700;margin:4px 0 8px 0;line-height:1.3}
.ui2-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:8px 0}
.ui2-card{border:1px solid rgba(128,128,128,.4);border-radius:10px;padding:10px 12px;min-width:0;
  overflow-wrap:anywhere}
.ui2-card__title{font-size:.85rem;opacity:.8}
.ui2-card__value{font-size:1.25rem;font-weight:700;margin:2px 0;line-height:1.3}
.ui2-card__value--blank{opacity:.5}
.ui2-card__chips{display:flex;flex-wrap:wrap;gap:4px;margin:2px 0}
.ui2-card__detail,.ui2-row__detail{font-size:.8rem;opacity:.75}
.ui2-chip{display:inline-block;border:1px solid currentColor;border-radius:999px;padding:1px 8px;
  font-size:.78rem;line-height:1.5;background:rgba(128,128,128,.08)}
/* 文字色對深色底 #0e1117（.streamlit/config.toml backgroundColor）與疊 tint 後皆 ≥4.5:1（Visual Fidelity Gate V8；
   tests/test_ui2_chip_contrast.py 解析本檔強制）。tint 的 rgba 沿用原色相，不隨文字色改。 */
.ui2-chip--positive{color:#3fb950;background:rgba(26,127,55,.12)}
.ui2-chip--warning{color:#d29922;background:rgba(183,121,31,.14)}
.ui2-chip--danger{color:#ff7b72;background:rgba(198,40,40,.12);font-weight:600}
.ui2-chip--neutral{opacity:.85}
/* 三語意軸的第二載體（樣式；字樣本身已互斥）：資料語意＝實線、判定結果＝雙線、capability＝虛線 */
.ui2-chip--axis-data{border-style:solid}
.ui2-chip--axis-judgement{border-style:double;border-width:3px;padding:0 7px}
.ui2-chip--axis-capability{border-style:dashed}
.ui2-empty{border:1px dotted rgba(128,128,128,.5);border-radius:8px;padding:6px 10px;margin:4px 0}
.ui2-empty__reason{font-size:.8rem;opacity:.75}
.ui2-freshrow .ui2-chip{max-width:100%;box-sizing:border-box;overflow-wrap:anywhere;border-radius:12px;padding:1px 10px}   /* 長來源文字換行時不成貼邊的長膠囊 */
.ui2-freshrow{display:flex;flex-wrap:wrap;gap:4px;align-items:center;font-size:.75rem;opacity:.85;margin-top:4px}
.ui2-fresh--missing{opacity:.8}
.ui2-qa{border:1px solid rgba(128,128,128,.4);border-radius:10px;padding:4px 12px 8px 12px;margin:8px 0}
.ui2-qrow{padding:5px 0;border-bottom:1px solid rgba(128,128,128,.2);line-height:1.5}
.ui2-q{display:block;font-size:.7rem;opacity:.65}
.ui2-row{padding:6px 0;border-bottom:1px solid rgba(128,128,128,.2)}
.ui2-row__label{font-size:.8rem;opacity:.75}
.ui2-row__body{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.ui2-row__value{font-weight:600}
.ui2-ctawrap{margin:2px 0 0 0}
.ui2-cta{display:inline-block;border:2px solid currentColor;border-radius:8px;padding:6px 14px;font-weight:700}
.ui2-cta--disabled{opacity:.5;border-style:dashed}
.ui2-cta__reason{font-size:.78rem;opacity:.75;margin-top:2px}
.ui2-section-title{font-weight:700;margin:12px 0 2px 0}
@media (max-width:640px){.ui2-pagetitle{font-size:1.2rem}.ui2-card__value{font-size:1.1rem}}

/* ── DEC-146 頂部兩列導覽（桌機＝手機同一份 DOM；⛔ 左 rail、⛔ Drawer、⛔ JS）──
   第一列（.ui2-top1）＝Active Sheet／帳號入口狀態（Capability `⬜ 尚未提供`，非互動）；第二列＝五頁 radiogroup。
   fixed 在視窗頂端；內容以 `.block-container` 的 padding-top 讓出同高（--ui2-nav-h：桌機 28＋44＋1px；手機第一列 40px 兩行→ 85px）。
   手機：第二列在**自身容器內**橫向捲動（overflow-x:auto；頁面本身 ⛔ 水平捲動），第 5 項（🗂 資料）可觸控滑動／Tab／方向鍵到達；
   桌機：五項平分寬度全可見。選中態＝`● ` 符號＋粗體＋底線＋原生 radio checked（顏色不是唯一載體）。
   選擇器不依賴 Streamlit 內部 class（1.56＝BaseWeb `data-baseweb`、1.59＝react-aria `stRadioOption`，兩代 DOM 不同）：
   只用 `.st-key-ui2_nav`（container key）＋ `[role=radiogroup] > label` ＋ `input:checked`。 */
:root{--ui2-nav-bg:#161b22;--ui2-nav-fg:#e6edf3;--ui2-nav-h:73px}
.st-key-ui2_nav{position:fixed;top:0;left:0;right:0;z-index:999995;margin:0 !important;padding:0 !important;gap:0 !important;
  box-sizing:border-box;background:var(--ui2-nav-bg);color:var(--ui2-nav-fg);border-bottom:1px solid rgba(128,128,128,.45);
  padding-left:env(safe-area-inset-left,0px) !important;padding-right:env(safe-area-inset-right,0px) !important}
.st-key-ui2_nav>*,.st-key-ui2_nav [data-testid="stRadio"]{width:100% !important;max-width:none !important;margin:0 !important;padding:0 !important}
.st-key-ui2_nav [data-testid="stWidgetLabel"]{display:none}
.st-key-ui2_nav [data-testid="stMarkdownContainer"]{margin:0 !important}   /* Streamlit 預設 margin-bottom:-1rem 會把第一列壓扁成 12px */
.ui2-top1{display:flex;justify-content:space-between;align-items:center;gap:0 8px;height:28px;box-sizing:border-box;padding:0 12px;
  font-size:.75rem;line-height:1.2;overflow:hidden}
.ui2-top1__item{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;min-width:0}
.ui2-top1 .ui2-chip{font-size:.7rem;line-height:1.3;padding:0 6px}
/* 資料模式標示（併入第一列；沿用 .ui2-banner 的 role=note 與文字契約）：單行、不折行、不截斷 */
.ui2-top1__mode{display:inline-flex;align-items:center;min-width:0;flex:0 1 auto}
.ui2-top1 .ui2-banner{border:0;border-radius:0;padding:0;margin:0;background:none;font-size:.75rem;line-height:1.2;white-space:nowrap}
.ui2-top1 .ui2-banner__note{font-size:.7rem}
@media (max-width:768px){   /* 手機：第一列固定兩行（標示一行、Sheet／帳號一行），高度固定、導覽讓位同步加高 */
  .ui2-top1{flex-wrap:wrap;height:40px;align-content:center;gap:2px 8px}
  .ui2-top1__mode{order:-1;flex:1 0 100%}
  :root{--ui2-nav-h:85px}
}
@media (max-width:359px){.ui2-top1 .ui2-banner{font-size:.68rem}.ui2-top1 .ui2-banner__note{font-size:.64rem}}
.st-key-ui2_nav [role="radiogroup"]{display:flex !important;flex-wrap:nowrap !important;gap:0 !important;width:100%;margin:0;
  align-items:stretch !important;overflow-x:auto;overflow-y:hidden;overscroll-behavior-x:contain;scrollbar-width:none;scroll-padding-inline:5.5rem}   /* 方向鍵／Tab 聚焦（input 在 label 左端）時連同整個 label 捲入視野 */
.st-key-ui2_nav [role="radiogroup"]::-webkit-scrollbar{display:none}
/* position:relative：Streamlit 的視覺隱藏 radio（絕對定位 1px）才會錨在各自的 label 而非固定導覽左緣；否則方向鍵／Tab 聚焦時瀏覽器不會把該項捲入視野 */
.st-key-ui2_nav [role="radiogroup"]>label{position:relative;flex:1 0 auto;margin:0 !important;cursor:pointer;height:44px;box-sizing:border-box;
  display:flex !important;align-items:center;justify-content:center;border:0 solid transparent;border-bottom-width:3px;padding:0 14px}
.st-key-ui2_nav [role="radiogroup"]>label div:not(:empty){display:flex;align-items:center;justify-content:inherit;
  width:100%;min-width:0;margin:0}
.st-key-ui2_nav [role="radiogroup"]>label *:has(>div:empty):not(:has(p)){display:none !important}   /* 隱藏圓點：當前頁改用符號＋粗體＋底線 */
.st-key-ui2_nav [role="radiogroup"]>label p{margin:0;font-size:.85rem;line-height:1.2;white-space:nowrap}
.st-key-ui2_nav [role="radiogroup"]>label:has(input:checked){font-weight:700;border-bottom-color:currentColor}
.st-key-ui2_nav [role="radiogroup"]>label:has(input:checked) p::before{content:"● ";font-size:.7em}
.st-key-ui2_nav [role="radiogroup"]>label:has(input:focus-visible){outline:2px solid currentColor;outline-offset:-2px}
@media (min-width:769px){
  .st-key-ui2_nav [role="radiogroup"]>label{flex:1 1 0;min-width:0}
}
/* 讓位高度＝導覽高 + 4px − 2rem：導覽 container 在 DOM 最前（Tab 順序最先），其 0 高的外層包裝在 Streamlit 的 1rem 元素間距上多佔 1rem（連同 CSS 注入元素共 2rem），
   這裡扣回（⛔ 讓第一個內容元素比「導覽高 + 4px」更低；量測見 evidence 的 title.top） */
@media (prefers-reduced-motion:reduce){.st-key-ui2_nav,.st-key-ui2_nav *{transition:none !important;animation:none !important;scroll-behavior:auto !important}}   /* 1.56（BaseWeb）的 radio 內部元件帶 .2s transition */
.block-container{padding-top:calc(var(--ui2-nav-h) + .25rem - 2rem) !important}
@media (max-width:768px){.block-container{padding-bottom:5rem !important}}
/* 內容底部保留量加上 safe-area（iOS 家的指示條）：僅在瀏覽器支援 env() 時覆寫；Chromium 實測為 0（不變）、iOS 未驗 */
@supports (padding-bottom:env(safe-area-inset-bottom)){
  @media (max-width:768px){.block-container{padding-bottom:calc(5rem + env(safe-area-inset-bottom,0px)) !important}}
}

/* ── Batch 3：📊 今日結論／今日主要風險、🎯 雙模式＋搜尋、👤 帳戶 skeleton ── */
.ui2-qrow--concl .ui2-concl__text{display:block;font-weight:600;line-height:1.45}
.ui2-risk{border:1px solid rgba(128,128,128,.4);border-radius:10px;padding:6px 12px 8px 12px;margin:8px 0;line-height:1.5}
.ui2-ctxline{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:.78rem}
.ui2-ctxline__item{white-space:nowrap}
.ui2-search{display:flex;gap:8px;align-items:center;margin:4px 0 2px 0}
.ui2-searchbox{flex:1 1 auto;min-width:0;border:1px dashed currentColor;border-radius:8px;padding:6px 10px;opacity:.65;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ui2-search .ui2-ctawrap{flex:0 0 auto;margin:0}
.ui2-search__hint{font-size:.78rem;margin:0 0 4px 0}
.ui2-snapshot{display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:6px;margin:6px 0}
.ui2-dim{border:1px solid rgba(128,128,128,.4);border-radius:8px;padding:5px 8px;min-width:0;overflow-wrap:anywhere;font-size:.85rem}
.ui2-lookup__head{margin:6px 0 2px 0}
.ui2-lookup__add{margin:6px 0 2px 0}
.ui2-account{margin:6px 0}
.ui2-account__btns{display:flex;flex-wrap:wrap;gap:6px 10px}
.ui2-account__btns .ui2-ctawrap{margin:0}
@media (min-width:769px){
  .ui2-m-l1{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:8px 0}
  .ui2-m-l1>.ui2-qa{display:contents}
  .ui2-m-l1 [data-ui2-q]{border:1px solid rgba(128,128,128,.4);border-radius:10px;padding:6px 12px;grid-column:1/-1}
  .ui2-m-l1 [data-ui2-q="q4"]{grid-row:1}      /* 更新 CTA 在今日結論之前（DEC-117 Q5／Wireframes §2.2） */
  .ui2-m-l1 [data-ui2-q="concl"]{grid-row:2}
  .ui2-m-l1 [data-ui2-q="q1"]{grid-column:1;grid-row:3}
  .ui2-m-l1 [data-ui2-q="ctx"]{grid-column:2;grid-row:3}
  .ui2-m-l1>.ui2-risk{grid-column:3;grid-row:3;margin:0}
  .ui2-m-l1 [data-ui2-q="q2"]{grid-row:4}
  .ui2-m-l1 [data-ui2-q="q3"]{grid-row:5}
}
/* 💼 持股（Wireframes §4.2／W-11，客戶 Q3 核准）：標題＋第一屏同一容器 `.ui2-h-l1`。
   手機：標題與第一屏間距補回原本兩個 Streamlit 元素容器之間的 16px（逐像素與舊版相同）。
   桌機（≥769px）：header 列＝標題＋主 CTA（CTA 絕對定位於右上；標題預留高度）；其下三 tile＝Risk Cap／目前曝險／組合狀態；
   今日需處理、下一步各一列。只重排既有元素，DOM 順序與 data-ui2-q 錨點不變；.ui2-qa 保持真實盒（量測以其頂緣為準，⛔ display:contents）。 */
.ui2-h-l1>.ui2-qa{margin-top:16px}
@media (min-width:769px){
  .ui2-h-l1{position:relative}
  .ui2-h-l1>.ui2-pagetitle{display:flex;align-items:center;min-height:4rem;box-sizing:border-box;margin:0}
  .ui2-h-l1>.ui2-qa{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0;border:0;padding:0;border-radius:0}
  .ui2-h-l1 [data-ui2-q]{border:1px solid rgba(128,128,128,.4);border-radius:10px;padding:6px 12px;grid-column:1/-1;min-width:0}
  .ui2-h-l1 [data-ui2-q="q4"]{position:absolute;top:0;right:0;border:0;padding:0;text-align:right}
  .ui2-h-l1 [data-ui2-q="ctx"]:nth-child(2){grid-column:1;grid-row:1}
  .ui2-h-l1 [data-ui2-q="ctx"]:nth-child(3){grid-column:2;grid-row:1}
  .ui2-h-l1 [data-ui2-q="q1"]{grid-column:3;grid-row:1}
  .ui2-h-l1 [data-ui2-q="q2"]{grid-row:2}
  .ui2-h-l1 [data-ui2-q="q3"]{grid-row:3}
}
/* 💼 持股 W-11 批 1（DEC-141）：狀態行／建議持股水位空槽／Primary 空槽／持股表欄名。⛔ 圖、⛔ 紅、⛔ 假列。
   DOM＝手機順序（建議持股水位→OneBrain→Primary→持股表）；桌機 grid：OneBrain／〔Primary｜建議持股水位〕／持股表。 */
.ui2-h-status{display:flex;flex-wrap:wrap;gap:2px 14px;margin:6px 0 0 0;font-size:.85rem;line-height:1.5}
.ui2-h-status__seg{white-space:nowrap}
.ui2-h-status__seg[data-seg="portfolio"]{white-space:normal;overflow-wrap:anywhere;min-width:0}
.ui2-h-body{display:flex;flex-direction:column;gap:8px;margin-top:8px}
.ui2-h-body>*{min-width:0;margin:0}
.ui2-h-primary{display:flex;align-items:center;gap:4px 10px;padding:6px 12px}
.ui2-h-primary .ui2-section-title{margin:0}
.ui2-h-primary .ui2-primary-slot__reason,.ui2-h-primary .ui2-primary-slot__spec{display:none}
.ui2-h-table{border:1px solid rgba(128,128,128,.4);border-radius:10px;padding:2px 12px 8px 12px}
.ui2-ht{width:100%;border-collapse:collapse;table-layout:fixed;font-size:.85rem}
.ui2-ht th{text-align:left;font-weight:600;padding:4px 6px;border-bottom:1px solid rgba(128,128,128,.4);overflow-wrap:anywhere}
.ui2-ht__x{display:none}
.ui2-ht__more{font-size:.75rem;opacity:.75;margin:4px 0 0 0}
.ui2-ht__empty{display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;padding:8px 0 0 0}
@media (min-width:769px){
  .ui2-h-status{margin:0 0 8px 0}
  .ui2-h-body{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);grid-template-areas:"ob ob" "pr cap" "tb tb";gap:8px 12px}
  .ui2-h-ob{grid-area:ob}
  .ui2-h-primary{grid-area:pr;display:block;min-height:240px;padding:2px 12px 8px 12px}
  .ui2-h-primary .ui2-section-title{margin:8px 0 4px 0}
  .ui2-h-primary .ui2-primary-slot__reason,.ui2-h-primary .ui2-primary-slot__spec{display:revert}
  .ui2-h-cap{grid-area:cap}
  .ui2-h-table{grid-area:tb}
  .ui2-ht__x{display:table-cell}
  .ui2-ht__more{display:none}
}
/* P2：OneBrain Outlook（上移後）與台股 Primary 誠實空槽——依內容高度；灰底說明、⛔ 紅、⛔ 圖 */
.ui2-m-onebrain .ui2-row{border-bottom:0;padding:2px 0 4px 0}
@media (min-width:769px){
  .ui2-m-onebrain{display:flex;flex-wrap:wrap;align-items:baseline;gap:0 14px}      /* 桌機單行：標題＋⬜ 尚未提供＋原因 */
  .ui2-m-onebrain .ui2-section-title{margin:12px 0 4px 0}
  .ui2-m-onebrain .ui2-row{padding:0;display:flex;flex-wrap:wrap;align-items:center;gap:0 10px}
}
.ui2-primary-slot{border:1px dashed rgba(128,128,128,.55);border-radius:10px;padding:2px 12px 8px 12px;margin:8px 0;
  background:rgba(128,128,128,.10)}
.ui2-primary-slot .ui2-section-title{margin:8px 0 4px 0}
.ui2-primary-slot__body{display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px}
.ui2-primary-slot__reason{font-size:.8rem;opacity:.75}
.ui2-primary-slot__spec{font-size:.75rem;opacity:.8;margin-top:4px;line-height:1.5;overflow-wrap:anywhere}
/* 市場頁更新 CTA 列（頂部）：按鈕與原因同列（手機窄時才折行），省去原本獨立一行的原因高度 */
.ui2-qrow--cta-top .ui2-ctawrap{display:flex;flex-wrap:wrap;align-items:center;gap:2px 10px;margin:0}
.ui2-qrow--cta-top .ui2-cta__reason{margin:0}
/* 🎯 模式切換（膠囊式 radio；DOM 無關寫法同導覽：只用 container key＋role＋input:checked） */
.st-key-ui2_target_mode_box [data-testid="stWidgetLabel"]{display:none}
.st-key-ui2_target_mode_box [role="radiogroup"]{display:flex !important;gap:8px !important;width:100%;margin:0;flex-wrap:nowrap}
.st-key-ui2_target_mode_box [role="radiogroup"]>label{flex:1 1 0;min-width:0;margin:0 !important;cursor:pointer;
  display:flex !important;align-items:center;justify-content:center;box-sizing:border-box;
  border:1px solid rgba(128,128,128,.55);border-radius:999px;padding:6px 8px}
.st-key-ui2_target_mode_box [role="radiogroup"]>label div:not(:empty){display:flex;align-items:center;
  justify-content:inherit;width:100%;min-width:0;margin:0}
.st-key-ui2_target_mode_box [role="radiogroup"]>label *:has(>div:empty):not(:has(p)){display:none !important}
.st-key-ui2_target_mode_box [role="radiogroup"]>label p{margin:0;font-size:.9rem;line-height:1.2;white-space:nowrap}
.st-key-ui2_target_mode_box [role="radiogroup"]>label:has(input:checked){font-weight:700;border-width:2px;
  background:rgba(128,128,128,.14)}
.st-key-ui2_target_mode_box [role="radiogroup"]>label:has(input:checked) p::before{content:"● ";font-size:.7em}
.st-key-ui2_target_mode_box [role="radiogroup"]>label:has(input:focus-visible){outline:2px solid currentColor;outline-offset:2px}
</style>
"""
