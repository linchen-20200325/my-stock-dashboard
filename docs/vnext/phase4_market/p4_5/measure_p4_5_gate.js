// Phase 4 P4-5：沿用 p4_4 `measure_p4_4_gate.js`（量測算法未改，只換標頭）；DEC-119 F1 圖 A 改自訂 vega-lite 後重量測。
// 用法（repo 根目錄；harness 已在 PORT，預設 8571）：
//   NODE_PATH=/opt/node-tools/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node docs/vnext/phase4_market/p4_5/measure_p4_5_gate.js <outdir>
// 輸出：JSON 到 stdout；截圖 <outdir>/app_market_<state>_<1440|390>[_tall].png（第一屏＋全頁）。
// state = loaded | cold | report | partial（harness 夾具；report／partial＝預置更新報告）
// 補足 measure_p4_1／measure_p4_2 沒量的 Gate 項：A3（外露字數）、A4（卡面字數／卡高）、A5（同列卡高差／空洞）、
//   A7（Top-N）、A8（外露 >32 字句清單）、A9／V9（Missing 符號集合）、A10、A11（KPI 區塊高／單一元素占屏比／水平捲動）、
//   V3（核心數字）、V8、V10（工程字樣）、V11（title= 承載資訊）、Q10（第一屏可見字數）。
const { chromium } = require('playwright');
const OUT = process.argv[2] || '.';
const PORT = process.env.PORT || 8571;
const ENG = ['線框', 'SSOT', 'digest', 'expander', 'widget', 'Gate', 'C2b', 'unwired', 'session', 'L0', 'L1', 'L2', 'L3', 'L4', 'L5', 'warroom', 'eps_high', 'judged_count', '鐵律', 'schema', 'fallback', 'parquet', 'provenance'];

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

const PROBE = ([vh, ENG]) => {
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
  const inClosed = el => { const d = el.closest('details'); return !!(d && !d.open && !el.closest('summary')); };
  // 可見文字：以最近的 block 祖先聚合文字節點
  const blocks = new Map();
  const tw = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = tw.nextNode())) {
    const t = (n.nodeValue || '').replace(/\s+/g, ' ').trim();
    if (!t) continue;
    let pe = n.parentElement;
    if (!pe || inClosed(pe)) continue;
    const r = pe.getBoundingClientRect();
    if (r.height === 0 || r.width === 0) continue;
    let b = pe;
    while (b && b !== main && /^(inline|contents)/.test(getComputedStyle(b).display)) b = b.parentElement;
    if (!b) continue;
    if (b.closest('svg')) continue;
    blocks.set(b, (blocks.get(b) || '') + ' ' + t);
  }
  const leaves = [...blocks.entries()].map(([el, t]) => ({ ...abs(el), t: t.trim().replace(/keyboard_arrow_\w+/g, '').trim() })).filter(l => l.t);
  const chars = s => s.replace(/\s+/g, '').length;
  const total = leaves.reduce((a, l) => a + chars(l.t), 0);
  const firstScreen = leaves.filter(l => l.y < usable);
  const fsChars = firstScreen.reduce((a, l) => a + chars(l.t), 0);
  const long = leaves.filter(l => chars(l.t) > 32).map(l => ({ y: l.y, n: chars(l.t), t: l.t.slice(0, 120) }));
  // 卡片（具名容器）
  const box = k => { const e = document.querySelector('.st-key-' + k); if (!e) return null; const a = abs(e);
    const kids = [...e.querySelectorAll('*')].filter(c => !inClosed(c) && c.getBoundingClientRect().height > 0);
    const lastB = Math.max(...kids.map(c => abs(c).b), a.b);
    const face = leaves.filter(l => l.y >= a.y && l.b <= a.b + 1 && l.x >= a.x - 1 && l.x < a.x + a.w).map(l => l.t).join(' ');
    return { ...a, faceChars: chars(face), face: face.slice(0, 200) }; };
  const cards = { regime: box('p4m_box_regime'), water: box('p4m_box_water'), risk: box('p4m_box_risk'), alerts: box('p4m_box_alerts') };
  const core = document.querySelector('.st-key-p4m_core_tiles');
  const coreBox = core ? abs(core) : null;
  const tiles = ['regime', 'water', 'risk'].map(k => cards[k]).filter(Boolean);
  const kpi = tiles.length ? { y: Math.min(...tiles.map(t => t.y)), b: Math.max(...tiles.map(t => t.b)) } : null;
  if (kpi) kpi.h = kpi.b - kpi.y;
  const heights = tiles.map(t => t.h);
  // 第一屏單一元素最高（L1 具名容器＋圖區容器＋ L1 內元素）
  const elems = [...document.querySelectorAll('.st-key-p4m_l1 [data-testid="stElementContainer"], .st-key-p4m_l1 [class*="st-key-p4m_box"], [class*="st-key-p4m_primary"], [class*="st-key-p4m_secondary"]')]
    .filter(e => !inClosed(e)).map(e => ({ cls: ([...e.classList].find(c => c.startsWith('st-key-')) || e.getAttribute('data-testid') || '').slice(0, 40), ...abs(e) }));
  const tallest = elems.reduce((a, e) => (e.h > a.h ? e : a), { h: 0 });
  // 工程字樣（外露層）
  const allText = leaves.map(l => l.t).join('\n');
  const eng = {};
  for (const w of ENG) { const c = allText.split(w).length - 1; if (c) eng[w] = c; }
  // Missing 符號集合（外露層，逐行）
  const missing = [...new Set(leaves.flatMap(l => l.t.split(/(?<=[。）)])|\s{2,}/).filter(s => /[⬜▨⛔⟳⊘◧]/.test(s)).map(s => s.trim().slice(0, 50))))];
  const symbols = [...new Set((allText.match(/[⬜▨⛔⟳⊘◧🔴⚠]/g) || []))];
  // hover-only
  const titles = [...main.querySelectorAll('[title]')].filter(e => !inClosed(e)).map(e => e.getAttribute('title').slice(0, 40));
  const titlesAll = [...document.querySelectorAll('[title]')].map(e => e.getAttribute('title').slice(0, 40));
  // 紅色錯誤（st.error）與灰
  const errs = [...main.querySelectorAll('[data-testid="stAlertContentError"]')].filter(e => !inClosed(e)).map(e => (e.innerText || '').slice(0, 60));
  // chips 數（第一屏）
  const chips = [...main.querySelectorAll('.cp-chip')].filter(e => !inClosed(e) && abs(e).y < usable).map(e => (e.innerText || '').trim());
  return {
    vh, usable, bottomNav, scrollH: sc.scrollHeight, docScrollW: document.documentElement.scrollWidth, docClientW: document.documentElement.clientWidth,
    hScroll: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    totalChars: total, firstScreenChars: fsChars, longSentences: long, cards, coreBox, kpi, tileHeights: heights,
    tileHeightSpreadPct: heights.length ? Math.round(100 * (Math.max(...heights) - Math.min(...heights)) / Math.max(...heights)) : null,
    tileHeightSpreadPx: heights.length ? Math.max(...heights) - Math.min(...heights) : null,
    tallestElement: tallest, tallestPctOfVh: Math.round(100 * tallest.h / vh),
    eng, symbols, missingLines: missing, titles, titlesAll, errs, chipsFirstScreen: chips,
    firstScreenLeaves: firstScreen.map(l => ({ y: l.y, n: chars(l.t), t: l.t.slice(0, 80) })),
  };
};

(async () => {
  const b = await chromium.launch({ args: ['--no-sandbox'] });
  const res = {};
  for (const [state, q] of [['loaded', ''], ['cold', '&cold=1'], ['report', '&report=1'], ['partial', '&report=partial']]) {
    for (const [vn, w, h] of [['1440', 1440, 900], ['390', 390, 844]]) {
      const ctx = await b.newContext({ viewport: { width: w, height: h } });
      const p = await ctx.newPage();
      await p.goto(`http://localhost:${PORT}/?p=market${q}`, { waitUntil: 'networkidle' });
      await p.waitForSelector('text=📊 市場', { timeout: 90000 });
      await waitIdle(p);
      await p.evaluate(() => { for (const e of [document.querySelector('[data-testid="stMain"]'), document.querySelector('[data-testid="stAppViewContainer"]'), document.scrollingElement]) if (e) e.scrollTop = 0; });
      await p.waitForTimeout(1500);
      await p.screenshot({ path: `${OUT}/app_market_${state}_${vn}.png` });
      res[`${state}/${vn}`] = await p.evaluate(PROBE, [h, ENG]);
      const sh = Math.min(res[`${state}/${vn}`].scrollH, 8000);
      await p.setViewportSize({ width: w, height: sh });
      await waitIdle(p, 1500);
      await p.screenshot({ path: `${OUT}/app_market_${state}_${vn}_tall.png` });
      await ctx.close();
    }
  }
  console.log(JSON.stringify(res));
  await b.close();
})();
