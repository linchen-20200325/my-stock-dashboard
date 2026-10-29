// Visual Fidelity 量測（開發工具）：開 harness_app.py，截 1440×900／390×844 第一屏＋全頁長圖，並量測 DOM。
// 用法：node measure_app.js <outdir> <market|target|hold> [cold]
// 環境變數：PORT（預設 8571）、EXTRA（附加 query，如 report=1 或 realflow=1）、TAG（輸出檔名後綴）。
// 輸出：<outdir>/app_<page>[_cold]<TAG>_<1440|390>.png 與 _tall.png；量測 JSON 印到 stdout。
const {chromium} = require('playwright');
const OUT = process.argv[2];
const PAGE = process.argv[3];
const COLD = process.argv[4] === 'cold';
const BASE = `http://localhost:${process.env.PORT || 8571}/`;

async function waitIdle(p, ms = 1500) {
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

async function measure(p, vh) {
  return await p.evaluate((vh) => {
    const sc = [document.querySelector('[data-testid="stMain"]'), document.querySelector('[data-testid="stAppViewContainer"]'), document.scrollingElement]
      .find(e => e && e.scrollHeight > e.clientHeight + 5 && getComputedStyle(e).overflowY !== 'visible') || document.scrollingElement;
    const st = sc.scrollTop || 0;
    const main = document.querySelector('[data-testid="stMainBlockContainer"]');
    const mr = main.getBoundingClientRect();
    const abs = el => { const r = el.getBoundingClientRect(); return {y: Math.round(r.top + st), h: Math.round(r.height), x: Math.round(r.left), w: Math.round(r.width)}; };
    const hidden = el => { const r = el.getBoundingClientRect(); if (r.height === 0 || r.width === 0) return true;
      const d = el.closest('details'); if (d && !d.open && !el.closest('summary')) return true; return false; };
    const txt = el => (el.innerText || '').replace(/\s+/g, '').length;
    const tid = el => el.getAttribute('data-testid') || '';
    // leaves
    const leaves = [...main.querySelectorAll('[data-testid="stElementContainer"]')].filter(e => !hidden(e)).map(e => {
      const inner = e.querySelector('[data-testid]');
      const kind = inner ? tid(inner) : '';
      return {kind, ...abs(e), chars: txt(e), t: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 70)};
    });
    const charts = [...main.querySelectorAll('[data-testid="stVegaLiteChart"], [data-testid="stPlotlyChart"], [data-testid="stArrowVegaLiteChart"], canvas.marks')]
      .filter(e => !hidden(e) && !e.closest('[data-testid="stDataFrame"]')).map(e => ({kind: tid(e) || e.tagName, ...abs(e)}));
    const uniqCharts = charts.filter(c => c.kind !== 'CANVAS');
    const dfs = [...main.querySelectorAll('[data-testid="stDataFrame"]')].filter(e => !hidden(e)).map(e => {
      const g = e.querySelector('[role="grid"], [role="table"], table');
      return {...abs(e), rows: g ? Number(g.getAttribute('aria-rowcount') || g.querySelectorAll('tr').length) : null};
    });
    const tables = [...main.querySelectorAll('table')].filter(e => !hidden(e) && !e.closest('[data-testid="stDataFrame"]')).map(e => ({...abs(e), rows: e.querySelectorAll('tbody tr, tr').length, cls: e.className}));
    const expanders = [...main.querySelectorAll('[data-testid="stExpander"]')].filter(e => !hidden(e)).map(e => ({...abs(e), label: (e.querySelector('summary') || e).innerText.split('\n')[0].slice(0, 50), open: !!(e.querySelector('details') || {}).open}));
    const borders = [...main.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stVerticalBlock"]')].filter(e => {
      if (hidden(e)) return false; const cs = getComputedStyle(e); return parseFloat(cs.borderTopWidth) > 0 && cs.borderTopStyle !== 'none';
    }).map(e => ({...abs(e), chars: txt(e), head: (e.innerText || '').split('\n')[0].slice(0, 40)}));
    const htmlCards = [...main.querySelectorAll('.stMarkdown div[class]')].filter(e => {
      if (hidden(e)) return false; const cs = getComputedStyle(e);
      const isCard = parseFloat(cs.borderTopWidth) > 0 && parseFloat(cs.borderRadius) > 0 && e.getBoundingClientRect().height > 30;
      return isCard && !e.parentElement.closest('.stMarkdown div[class]')?.matches?.('*') ? isCard : false;
    }).map(e => ({...abs(e), chars: txt(e), cls: e.className.slice(0, 30), head: (e.innerText || '').split('\n')[0].slice(0, 40)}));
    const buttons = [...main.querySelectorAll('button')].filter(e => !hidden(e)).map(e => ({...abs(e), t: e.innerText.trim().slice(0, 30)})).filter(b => b.t);
    // outline: top-level children of first vertical block
    const vb = main.querySelector('[data-testid="stVerticalBlock"]');
    const outline = [...vb.children].filter(e => !hidden(e)).map(e => {
      const inner = tid(e) === 'stElementContainer' ? (e.querySelector('[data-testid]') ? tid(e.querySelector('[data-testid]')) : '') : tid(e);
      const ch = [...e.querySelectorAll('[data-testid="stVegaLiteChart"], [data-testid="stPlotlyChart"]')].filter(x => !hidden(x)).map(x => Math.round(x.getBoundingClientRect().height));
      return {kind: inner || tid(e), ...abs(e), chars: txt(e), charts: ch, t: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60)};
    });
    // ink grid on first screen within main content column
    const cell = 6, x0 = Math.max(0, mr.left), x1 = Math.min(window.innerWidth, mr.right);
    const top = (document.querySelector('[data-testid="stHeader"]') || {getBoundingClientRect: () => ({bottom: 0})}).getBoundingClientRect().bottom;
    const y0 = Math.max(0, top), y1 = vh;
    const gw = Math.ceil((x1 - x0) / cell), gh = Math.ceil((y1 - y0) / cell);
    const grid = new Uint8Array(gw * gh);
    const mark = r => { const a = Math.max(0, Math.floor((r.left - x0) / cell)), b = Math.min(gw - 1, Math.floor((r.right - x0) / cell));
      const c = Math.max(0, Math.floor((r.top - y0) / cell)), d = Math.min(gh - 1, Math.floor((r.bottom - y0) / cell));
      for (let j = c; j <= d; j++) for (let i = a; i <= b; i++) grid[j * gw + i] = 1; };
    const tw = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
    let n; while ((n = tw.nextNode())) { if (!n.textContent.trim()) continue; const pe = n.parentElement; if (!pe || hidden(pe)) continue;
      const rg = document.createRange(); rg.selectNodeContents(n); for (const r of rg.getClientRects()) if (r.bottom > y0 && r.top < y1) mark(r); }
    for (const e of main.querySelectorAll('canvas, svg, button, input, textarea, [data-baseweb="select"], img, [data-testid="stVegaLiteChart"]')) {
      if (hidden(e)) continue; const r = e.getBoundingClientRect(); if (r.bottom > y0 && r.top < y1 && r.width > 4) mark(r); }
    let ink = 0; for (const v of grid) ink += v;
    // vertical coverage by leaves on first screen
    const cov = new Uint8Array(Math.max(1, y1 - y0));
    for (const e of main.querySelectorAll('[data-testid="stElementContainer"]')) { if (hidden(e)) continue; const r = e.getBoundingClientRect();
      for (let y = Math.max(y0, Math.floor(r.top)); y < Math.min(y1, Math.ceil(r.bottom)); y++) cov[y - y0] = 1; }
    let covered = 0; for (const v of cov) covered += v;
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    const bn = [...document.querySelectorAll('div')].find(d => getComputedStyle(d).position === 'fixed' && d.getBoundingClientRect().bottom >= window.innerHeight - 2 && d.getBoundingClientRect().height < 120 && d.innerText.includes('市場'));
    return {scrollH: sc.scrollHeight, scrollerId: tid(sc) || sc.tagName, mainTop: Math.round(mr.top + st), mainX: Math.round(mr.left), mainW: Math.round(mr.width),
            headerBottom: Math.round(top), sidebarW: sidebar ? Math.round(sidebar.getBoundingClientRect().width) : 0,
            bottomNav: bn ? abs(bn) : null,
            inkRatioFirst: +(ink / grid.length).toFixed(3), vertCoverFirst: +(covered / cov.length).toFixed(3),
            outline, leaves, charts: uniqCharts, dfs, tables, expanders, borders, htmlCards, buttons,
            totalVisibleChars: leaves.reduce((a, l) => a + l.chars, 0)};
  }, vh);
}

async function flow(p) {
  if (PAGE === 'target' && !COLD) {
    const click = async (name) => { await p.getByRole('button', {name}).first().click(); await p.waitForTimeout(800); await waitIdle(p); };
    await click('🗺️ 載入板塊地圖');
    await click('🎯 開始選股');
    await click('🔍 查看此檔');
  }
}

(async () => {
  const b = await chromium.launch();
  const res = {};
  for (const [vn, w, h] of [['1440', 1440, 900], ['390', 390, 844]]) {
    const ctx = await b.newContext({viewport: {width: w, height: h}});
    const p = await ctx.newPage();
    await p.goto(BASE + '?p=' + PAGE + (COLD ? '&cold=1' : '') + (process.env.EXTRA ? '&' + process.env.EXTRA : ''), {waitUntil: 'networkidle'});
    await p.waitForSelector('text=' + {market: '📊 市場', target: '🎯 標的', hold: '💼 '}[PAGE], {timeout: 90000});
    await waitIdle(p, 2500);
    await flow(p);
    await p.evaluate(() => { for (const e of [document.querySelector('[data-testid="stMain"]'), document.querySelector('[data-testid="stAppViewContainer"]'), document.scrollingElement]) if (e) e.scrollTop = 0; });
    await p.waitForTimeout(1500);
    const tag = `${PAGE}${COLD ? '_cold' : ''}${process.env.TAG || ''}_${vn}`;
    await p.screenshot({path: `${OUT}/app_${tag}.png`});
    const m = await measure(p, h);
    const exc = await p.evaluate(() => [...document.querySelectorAll('[data-testid="stException"], [data-testid="stAlertContentError"]')].map(e => e.innerText.slice(0, 200)));
    m.errors = exc;
    // tall screenshot: enlarge viewport to full scroll height
    const H = Math.min(m.scrollH + 40, 30000);
    await p.setViewportSize({width: w, height: H});
    await p.waitForTimeout(2500);
    await p.screenshot({path: `${OUT}/app_${tag}_tall.png`});
    m.tallH = H;
    res[vn] = m;
    await ctx.close();
  }
  console.log(JSON.stringify(res));
  await b.close();
})();
