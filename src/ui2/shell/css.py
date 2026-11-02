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
</style>
"""
