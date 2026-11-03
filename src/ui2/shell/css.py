"""New UI2 CSS（`ui2-` 前綴；手機優先、保守）。

- 用 `currentColor`／半透明底色，亮暗主題皆可讀（⛔ 假設白底）。
- 卡片網格 `auto-fit minmax(150px,1fr)`：390px 寬為 2 欄、桌機自動多欄（⛔ 先做桌機再縮）。
- 顏色不是唯一載體：每個 chip 都有文字／符號（Freeze §4.1）。
"""
CSS = """
<style>
.block-container{padding-top:2.75rem !important;padding-bottom:2rem !important}
@media (max-width:640px){.block-container{padding-left:.9rem !important;padding-right:.9rem !important}}
.ui2-banner{border:1px dashed currentColor;border-radius:8px;padding:8px 12px;margin:0 0 12px 0;
  background:rgba(128,128,128,.10);font-size:.9rem;line-height:1.4}
.ui2-banner__note{display:block;opacity:.8;font-size:.8rem}
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

/* ── W-1 導覽（Wireframes §0.4／Freeze §16）：手機＝底部固定四格（53px）、桌機＝左側四項 ──
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
@media (max-width:768px){
  .st-key-ui2_nav{left:0;right:0;bottom:0;height:53px;border-top-width:1px}
  .st-key-ui2_nav [role="radiogroup"]{height:53px}
  .st-key-ui2_nav [role="radiogroup"]>label{border-top-width:3px;text-align:center}
  .st-key-ui2_nav [role="radiogroup"]>label:has(input:checked){border-top-color:currentColor}
  .block-container{padding-bottom:5rem !important}
}
@media (min-width:769px){
  .st-key-ui2_nav{top:0;left:0;bottom:0;width:11rem;border-right-width:1px;padding-top:4rem !important}
  .st-key-ui2_nav [role="radiogroup"]{flex-direction:column}
  .st-key-ui2_nav [role="radiogroup"]>label{flex:0 0 auto;justify-content:flex-start;padding:.7rem 1rem;
    border-left-width:4px}
  .st-key-ui2_nav [role="radiogroup"]>label:has(input:checked){border-left-color:currentColor}
  .block-container{padding-left:12.5rem !important}
}
</style>
"""
