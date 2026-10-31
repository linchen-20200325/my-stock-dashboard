// Phase 4 P4-2：📊 市場頁圖區量測（只量測，不改任何 app 檔；不被 app／test import；開發用）
// 用法（repo 根目錄；harness 已在 PORT，預設 8571）：
//   NODE_PATH=/opt/node-tools/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node docs/vnext/phase4_market/p4_2/measure_p4_2.js <outdir> [query 前綴，預設 p=market]
// 輸出：JSON 到 stdout；截圖 <outdir>/p4_2_<state>_<1440|390>_{first,zone}.png（第一屏、圖區）。state = loaded | cold | report | partial
// 量什麼（線框 §10 C1-7／C1-8／C3-1／C4-1～C4-6／C8-a）：
//   · 圖區 4 個具名容器的 y／h 與順序（Primary → 國際小倍數 → 圖 D → 圖 C）、Primary 緊接 AI 行
//   · Primary 原生圖：vega 圖高、y 軸刻度文字數、圖例是否存在
//   · 小倍數：格數（5）、每格高、每格可見文字（扣掉系列名後是否含數字 ⇒ D5=A）、placeholder 格
//   · 每張圖摺疊標籤（恰 1 個「▸ 為什麼／來源／限制／去哪補」）
//   · 橫向捲動：頁面與圖區容器 scrollWidth > clientWidth
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
  let bottomNav = 0;
  for (const e of document.querySelectorAll('[class*="st-key-nav4_bottom"]')) {
    const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
    if (cs.position === 'fixed' && cs.display !== 'none' && r.height > 0) bottomNav = Math.max(bottomNav, Math.round(r.height));
  }
  const usable = vh - bottomNav;
  const keys = { A: 'p4m_primary', B: 'p4m_secondary_intl', D: 'p4m_secondary_d', C: 'p4m_secondary_c' };
  const zone = {};
  for (const [k, key] of Object.entries(keys)) {
    const el = document.querySelector('.st-key-' + key);
    if (!el) { zone[k] = { found: false }; continue; }
    const folds = [...el.querySelectorAll('summary')].map(s => (s.innerText || '').replace(/keyboard_arrow_\w+/g, '').trim());
    zone[k] = { ...abs(el), inFirstScreen: abs(el).y < usable, scrollW: el.scrollWidth, clientW: el.clientWidth,
      overflowX: el.scrollWidth > el.clientWidth + 1, folds,
      title: ((el.querySelector('.cp-ch-title') || {}).innerText || '').trim(),
      chips: [...el.querySelectorAll('.cp-chip')].map(c => (c.innerText || '').trim()),
      say: ((el.querySelector('.cp-ch-say') || {}).innerText || '').trim().slice(0, 40),
      captionsOutside: [...el.querySelectorAll('[data-testid="stCaptionContainer"]')].filter(c => !c.closest('details')).map(c => (c.innerText || '').trim().slice(0, 60)),
      errorsOutside: [...el.querySelectorAll('[data-testid="stAlertContentError"]')].filter(c => !c.closest('details')).length,
    };
  }
  // Primary 原生圖
  const prim = document.querySelector('.st-key-p4m_primary');
  let chart = null;
  if (prim) {
    const v = prim.querySelector('[data-testid="stVegaLiteChart"], .stVegaLiteChart, .vega-embed');
    if (v) {
      const axisText = [...v.querySelectorAll('.role-axis text')].map(t => (t.textContent || '').trim()).filter(Boolean);
      const yAxis = [...v.querySelectorAll('.role-axis')].filter(a => a.getAttribute('aria-label') && /Y-axis/i.test(a.getAttribute('aria-label')));
      const legend = [...v.querySelectorAll('.role-legend text')].map(t => (t.textContent || '').trim()).filter(Boolean);
      const lines = v.querySelectorAll('.mark-line path, .role-mark path').length;
      chart = { ...abs(v), yAxisGroups: yAxis.length, axisTextCount: axisText.length, axisSample: axisText.slice(0, 6), legend, linePaths: lines };
    }
  }
  // 小倍數
  const sm = document.querySelector('.cp-sm');
  let smInfo = null;
  if (sm) {
    const cells = [...sm.querySelectorAll('.cp-sm-cell')].map(c => {
      const name = ((c.querySelector('.cp-sm-name') || {}).innerText || '').trim();
      const full = (c.innerText || '').trim();
      const rest = full.replace(name, '');
      return { name, h: Math.round(c.getBoundingClientRect().height), w: Math.round(c.getBoundingClientRect().width),
        hasSvg: !!c.querySelector('svg'), placeholder: ((c.querySelector('.cp-sm-missing') || {}).innerText || '').trim(),
        restText: rest.trim(), restHasDigit: /\d/.test(rest), svgText: [...c.querySelectorAll('svg text')].length };
    });
    const cols = new Set(cells.map(c => 0)).size;  // placeholder
    const xs = [...sm.querySelectorAll('.cp-sm-cell')].map(c => Math.round(c.getBoundingClientRect().left));
    smInfo = { ...abs(sm), nCells: cells.length, cells, nCols: new Set(xs).size, maxCellH: Math.max(0, ...cells.map(c => c.h)),
      anyDigitOutsideNames: cells.some(c => c.restHasDigit), anyTextInSvg: cells.some(c => c.svgText > 0) };
  }
  const ai = [...main.querySelectorAll('[data-testid="stCaptionContainer"]')].find(e => /^🤖 AI 投資總結/.test((e.innerText || '').trim()));
  const order = ['A', 'B', 'D', 'C'].filter(k => zone[k].found !== false).sort((a, b) => zone[a].y - zone[b].y);
  const gaps = [];
  const seq = ['A', 'B', 'D', 'C'];
  for (let i = 0; i < seq.length - 1; i++) if (zone[seq[i]].found !== false && zone[seq[i + 1]].found !== false) gaps.push(zone[seq[i + 1]].y - zone[seq[i]].b);
  return {
    vh, bottomNav, usable, scrollH: sc.scrollHeight, docScrollW: document.documentElement.scrollWidth, docClientW: document.documentElement.clientWidth,
    pageOverflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    zone, order, gapsBetweenZones: gaps, chart, sm: smInfo,
    aiLine: ai ? abs(ai) : null,
    primaryGapFromAi: (ai && zone.A.found !== false) ? zone.A.y - abs(ai).b : null,
    titleAttrInZone: [...document.querySelectorAll('.st-key-p4m_primary [title], .st-key-p4m_secondary_intl [title], .st-key-p4m_secondary_d [title], .st-key-p4m_secondary_c [title]')].map(e => e.getAttribute('title').slice(0, 30)),
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
      await p.waitForTimeout(1500);
      await p.screenshot({ path: `${OUT}/p4_2_${state}_${vn}_first.png` });
      res[`${state}/${vn}`] = await p.evaluate(PROBE, h);
      // 圖區截圖：捲到 Primary 容器、截圖區（Primary → 圖 C）
      const box = await p.evaluate(() => {
        const a = document.querySelector('.st-key-p4m_primary'); const c = document.querySelector('.st-key-p4m_secondary_c');
        if (!a || !c) return null; a.scrollIntoView({ block: 'start' });
        return true;
      });
      await p.waitForTimeout(600);
      await p.screenshot({ path: `${OUT}/p4_2_${state}_${vn}_zone.png`, fullPage: false });
      await ctx.close();
    }
  }
  console.log(JSON.stringify(res));
  await b.close();
})();
