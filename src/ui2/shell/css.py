"""New UI2 CSS（`ui2-` 前綴；手機優先、保守）。

- 用 `currentColor`／半透明底色，亮暗主題皆可讀（⛔ 假設白底）。
- 卡片網格 `auto-fit minmax(150px,1fr)`：390px 寬為 2 欄、桌機自動多欄（⛔ 先做桌機再縮）。
- 顏色不是唯一載體：每個 chip 都有文字／符號（Freeze §4.1）。
"""
CSS = """
<style>
.block-container{padding-top:2.75rem !important;padding-bottom:2rem !important}
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
.ui2-chip--positive{color:#1a7f37;background:rgba(26,127,55,.12)}
.ui2-chip--warning{color:#b7791f;background:rgba(183,121,31,.14)}
.ui2-chip--danger{color:#c62828;background:rgba(198,40,40,.12);font-weight:600}
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

/* ── W-1 導覽（Wireframes §0.4／Freeze §16；DEC-134／DEC-137）：手機＝左上 ☰＋左側抽屜（預設收合）、桌機＝左側四項 ──
   （手機原底部固定四格 53px 已由 DEC-134 取代；53px 現為「底部保留帶」＝Manage app／家的指示條可能遮擋區，量測線 791 不變）
   選擇器不依賴 Streamlit 內部 class（1.56＝BaseWeb `data-baseweb`、1.59＝react-aria `stRadioOption`，
   兩代 DOM 不同）：只用 `.st-key-ui2_nav`（container key）＋ `[role=radiogroup] > label` ＋ `input:checked`。 */
.st-key-ui2_nav{position:fixed;z-index:999990;margin:0 !important;padding:0 !important;gap:0 !important;
  background:var(--ui2-nav-bg);border:0 solid rgba(128,128,128,.45)}
.st-key-ui2_nav>*,.st-key-ui2_nav [data-testid="stRadio"]{width:100% !important;max-width:none !important}
.st-key-ui2_nav [role="radiogroup"]{display:flex !important;gap:0 !important;width:100%;margin:0;align-items:stretch !important}
.st-key-ui2_nav [role="radiogroup"]>label{flex:1 1 0;min-width:0;margin:0 !important;cursor:pointer;
  display:flex !important;align-items:center;justify-content:center;box-sizing:border-box;
  border:0 solid transparent;padding:0 2px}
.st-key-ui2_nav [role="radiogroup"]>label div:not(:empty){display:flex;align-items:center;justify-content:inherit;
  width:100%;min-width:0;margin:0}
.st-key-ui2_nav [role="radiogroup"]>label *:has(>div:empty):not(:has(p)){display:none !important}   /* 隱藏圓點：當前頁改用符號＋粗體＋色條 */
.st-key-ui2_nav [role="radiogroup"]>label p{margin:0;font-size:.85rem;line-height:1.2;white-space:nowrap}
.st-key-ui2_nav [role="radiogroup"]>label:has(input:checked){font-weight:700}
.st-key-ui2_nav [role="radiogroup"]>label:has(input:checked) p::before{content:"● ";font-size:.7em}
.st-key-ui2_nav [role="radiogroup"]>label:has(input:focus-visible){outline:2px solid currentColor;outline-offset:-2px}
.st-key-ui2_nav [data-testid="stWidgetLabel"]{display:none}
/* 導覽列自帶底色＋字色（取自 `.streamlit/config.toml` [theme] 的 secondaryBackgroundColor／textColor），
   避免依賴 Streamlit 無公開的主題變數；使用者若手動切 Light theme，導覽列仍為深色但字色同步，維持可讀。 */
:root{--ui2-nav-bg:#161b22;--ui2-nav-fg:#e6edf3}
.st-key-ui2_nav{color:var(--ui2-nav-fg)}
/* 關閉態抽屜整塊不留在無障礙樹（L-4：內層某 class 會把 visibility 設回 visible；零 JS 修法） */
.st-key-ui2_nav *{visibility:inherit !important}
@media (max-width:768px){
  .st-key-ui2_nav{z-index:999995;top:0;left:0;bottom:0;width:min(82vw,320px);box-sizing:border-box;border-right-width:1px;padding:3.6rem .75rem 1rem !important;
    transform:translateX(-105%);visibility:hidden;overflow-y:auto;transition:transform .2s ease, visibility 0s linear .2s}
  .st-key-ui2_nav [role="radiogroup"]{flex-direction:column}
  .st-key-ui2_nav [role="radiogroup"]>label{flex:0 0 auto;min-height:48px;justify-content:flex-start;padding:0 .5rem;border-left-width:4px}
  .st-key-ui2_nav [role="radiogroup"]>label:has(input:checked){border-left-color:currentColor}
  .stApp:has(.ui2-dr-toggle:checked) .st-key-ui2_nav{transform:none;visibility:visible;transition:transform .2s ease, visibility 0s}
  .stApp:has(.ui2-dr-toggle:checked) .ui2-dr-scrim{display:block}
  .block-container{padding-bottom:5rem !important}
}
@media (prefers-reduced-motion:reduce){.st-key-ui2_nav{transition:none !important}}
/* ☰（checkbox＋label；占既有 padding-top:2.75rem＝44px 頂部保留帶，⛔ 新增位移）與遮罩 */
.ui2-dr-btn{position:fixed;top:0;left:0;z-index:999996;min-height:44px;min-width:44px;box-sizing:border-box;padding:0 12px;display:flex;
  align-items:center;justify-content:center;background:var(--ui2-nav-bg);color:var(--ui2-nav-fg);border:1px solid rgba(128,128,128,.5);
  border-radius:8px;font:inherit;font-size:1.2rem;cursor:pointer}
.ui2-dr-scrim{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:999993}
.ui2-dr-toggle{position:fixed;top:0;left:0;width:44px;height:44px;margin:0;opacity:0;z-index:999997;cursor:pointer}
.ui2-dr-toggle:focus-visible+.ui2-dr-btn{outline:2px solid currentColor;outline-offset:2px}
.ui2-drawer-acct{margin-top:1rem;padding-top:.75rem;border-top:1px solid rgba(128,128,128,.45);font-size:.85rem;line-height:1.5}
.ui2-drawer-acct__title{font-weight:700}
.ui2-drawer-acct .ui2-ctawrap{margin:6px 0 2px 0}
.ui2-drawer-acct__more{font-size:.72rem;opacity:.7}
/* 內容底部保留量加上 safe-area（iOS 家的指示條）：僅在瀏覽器支援 env() 時覆寫；Chromium 實測為 0（不變）、iOS 未驗 */
@supports (padding-bottom:env(safe-area-inset-bottom)){
  @media (max-width:768px){.block-container{padding-bottom:calc(5rem + env(safe-area-inset-bottom,0px)) !important}}
}
@media (min-width:769px){
  .st-key-ui2_nav{top:0;left:0;bottom:0;width:11rem;border-right-width:1px;padding-top:4rem !important;overflow-y:auto}
  .ui2-dr-btn,.ui2-dr-scrim,.ui2-dr-toggle{display:none !important}   /* 桌機：無 ☰／遮罩（不建立第二個主導覽入口） */
  .st-key-ui2_nav>*:has(.ui2-drawer-acct){order:-1}      /* 桌機 rail：帳戶摘要在四頁之前（DEC-129 順序；手機抽屜為四頁→帳戶） */
  .st-key-ui2_nav .ui2-drawer-acct{margin:0 .75rem .75rem .75rem;padding:0 0 .75rem 0;border-top:0;border-bottom:1px solid rgba(128,128,128,.45)}
  .st-key-ui2_nav [role="radiogroup"]{flex-direction:column}
  .st-key-ui2_nav [role="radiogroup"]>label{flex:0 0 auto;justify-content:flex-start;padding:.7rem 1rem;
    border-left-width:4px}
  .st-key-ui2_nav [role="radiogroup"]>label:has(input:checked){border-left-color:currentColor}
  .block-container{padding-left:12.5rem !important}
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
