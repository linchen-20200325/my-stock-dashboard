// Phase 4 P4-1：📊 市場頁第一屏量測（只量測，不改任何 app 檔；不被 app／test import；開發用）
// 用法（repo 根目錄；harness 已在 PORT，預設 8571）：
//   NODE_PATH=/opt/node-tools/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node docs/vnext/phase4_market/p4_1/measure_p4_1.js <outdir> [query 前綴，預設 p=market]
// 輸出：JSON 到 stdout；截圖 <outdir>/p4_1_<state>_<1440|390>.png（第一屏）。state = loaded | cold | report | partial
// 量什麼（線框 §10 C1-1／C1-6／C1-7／C1-9／C1-10／C1-11）：
//   · L1 區塊的 DOM 順序（頁首 H2、更新選項、更新鈕、更新報告、結論標題、結論句、3 tile、⚡ bar、AI 行、圖A）
//   · 結論句頂端相對 H2（Q11）、tile 高、⚡ bar 底緣是否在第一屏（手機扣掉底部固定導覽）、頁首動作列（form）實高
const { chromium } = require('playwright');
const OUT = process.argv[2] || '.';
const BASEQ = process.argv[3] || 'p=market';
const PORT = process.env.PORT || 8571;

async function waitIdle(p, ms = 2500) {
  let quiet = 0;
  for (let i = 0; i < 240; i++) {
    const running = await p.evaluate(() => {
      const s = document.querySelector('[data-testid="stStatusWidget"]');
      return !!(s && /Running|執行/.test(s.innerText || '')) || !!document.querySelector('[data-testid="stSpinner"]');
    });
    quiet = running ? 0 : quiet + 250;
    if (quiet >= ms) return;
    await p.waitForTimeout(250);
  }
}

const PROBE = (vh) => {
  const sc = [document.querySelector('[data-testid="stMain"]'), document.querySelector('[data-testid="stAppViewContainer"]'), document.scrollingElement]
    .find(e => e && e.scrollHeight > e.clientHeight + 5 && getComputedStyle(e).overflowY !== 'visible') || document.scrollingElement;
  const st = sc.scrollTop || 0;
  const main = document.querySelector('[data-testid="stMainBlockContainer"]');
  const abs = el => { const r = el.getBoundingClientRect(); return { y: Math.round(r.top + st), h: Math.round(r.height), b: Math.round(r.bottom + st), x: Math.round(r.left), w: Math.round(r.width) }; };
  const hidden = el => { const r = el.getBoundingClientRect(); if (r.height === 0 || r.width === 0) return true; const d = el.closest('details'); return !!(d && !d.open && !el.closest('summary')); };
  // 底部固定導覽（手機）：position:fixed 且貼底的元素高度 → 第一屏可用高 = vh − 該高度
  let bottomNav = 0;
  for (const e of document.querySelectorAll('[class*="st-key-nav4_bottom"]')) {
    const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
    if (cs.position === 'fixed' && cs.display !== 'none' && r.height > 0) bottomNav = Math.max(bottomNav, Math.round(r.height));
  }
  const usable = vh - bottomNav;
  const h2 = [...main.querySelectorAll('h2')].find(h => /市場/.test(h.innerText));
  const h2y = h2 ? abs(h2).y : null;
  const leafs = [...main.querySelectorAll('[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"], summary, button, h4')].filter(e => !hidden(e));
  const first = (re) => leafs.find(e => re.test((e.innerText || '').trim()));
  const L1 = document.querySelector('.st-key-p4m_l1');
  const tilesRow = document.querySelector('.st-key-p4m_core_tiles [data-testid="stHorizontalBlock"]');
  const form = main.querySelector('[data-testid="stForm"]');
  const named = [
    ['H2', h2],
    ['更新選項', first(/^更新選項/)],
    ['更新鈕', first(/^🚀 更新今日戰情/)],
    ['更新報告', first(/上一次更新的結果/)],
    ['結論標題', first(/^今日結論（五項各自判斷/)],
    ['結論句', first(/^市場位階：.*台股趨勢：/)],
    ['tile_市場位階', first(/^市場位階$/)],
    ['tile_水位', first(/^建議總持股水位$/)],
    ['tile_風險', first(/^今日主要風險$/)],
    ['⚡bar', first(/^⚡ 需要處理/)],
    ['AI行', first(/^🤖 AI 投資總結/)],
    ['圖A', first(/^圖A/)],
  ];
  const blocks = named.map(([n, e]) => e ? { name: n, ...abs(e), relH2: h2y !== null ? abs(e).y - h2y : null, inFirstScreen: abs(e).b <= usable } : { name: n, found: false });
  const found = blocks.filter(b => b.found !== false);
  const orderByY = [...found].sort((a, b) => a.y - b.y || a.x - b.x).map(b => b.name);
  // ⚡ bar 的外框（含「🔍 查看依據」標題列）底緣
  const barEl = first(/^⚡ 需要處理/);
  const barBox = barEl ? barEl.closest('[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stVerticalBlock"]') : null;
  const tiles = tilesRow ? [...tilesRow.children].filter(c => !hidden(c)).map(c => ({ ...abs(c), head: (c.innerText || '').split('\n')[0].slice(0, 12) })) : [];
  const titles = [...main.querySelectorAll('[title]')].filter(e => !hidden(e) && e.getAttribute('title')).map(e => ({ title: e.getAttribute('title').slice(0, 40), tag: e.tagName }));
  const exps = [...main.querySelectorAll('[data-testid="stExpander"]')].filter(e => !hidden(e)).map(e => ({ y: abs(e).y, label: ((e.querySelector('summary') || e).innerText || '').replace(/keyboard_arrow_\w+/g, '').trim().split('\n')[0].slice(0, 40), open: !!(e.querySelector('details') || {}).open }));
  return {
    vh, bottomNav, usable, h2y, scrollH: sc.scrollHeight,
    blocks, orderByY,
    l1: L1 ? abs(L1) : null,
    headerForm: form ? abs(form) : null,
    alertsBox: barBox ? { ...abs(barBox), inFirstScreen: abs(barBox).b <= usable } : null,
    tiles, titlesVisible: titles, expandersVisible: exps.slice(0, 12),
    errorsVisible: [...main.querySelectorAll('[data-testid="stAlertContentError"], [data-testid="stException"]')].filter(e => !hidden(e)).map(e => (e.innerText || '').slice(0, 60)),
  };
};

(async () => {
  const b = await chromium.launch({ args: ['--no-sandbox'] });
  const res = {};
  for (const [state, q] of [['loaded', ''], ['cold', '&cold=1'], ['report', '&report=1'], ['partial', '&report=partial']]) {
    for (const [vn, w, h] of [['1440', 1440, 900], ['390', 390, 844]]) {
      const ctx = await b.newContext({ viewport: { width: w, height: h } });
      const p = await ctx.newPage();
      await p.goto(`http://localhost:${PORT}/?${BASEQ}${q}`, { waitUntil: 'networkidle' });
      await p.waitForSelector('text=📊 市場', { timeout: 90000 });
      await waitIdle(p);
      await p.evaluate(() => { for (const e of [document.querySelector('[data-testid="stMain"]'), document.querySelector('[data-testid="stAppViewContainer"]'), document.scrollingElement]) if (e) e.scrollTop = 0; });
      await p.waitForTimeout(1200);
      await p.screenshot({ path: `${OUT}/p4_1_${state}_${vn}.png` });
      res[`${state}/${vn}`] = await p.evaluate(PROBE, h);
      await ctx.close();
    }
  }
  console.log(JSON.stringify(res));
  await b.close();
})();
