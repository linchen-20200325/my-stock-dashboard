// Phase 4 P4-5：圖 A 圖例量測（DEC-119 題 1）。用法（harness 已在 PORT，預設 8571）：
//   NODE_PATH=/opt/node-tools/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node measure_p4_5_legend.js <outdir>
// 對每個 state（loaded／report／partial；cold 無圖）× viewport（390／1440）：圖寬高、圖例逐項（symbol＋label 聯集）的 x 範圍＋是否全在圖寬內、
// 圖例標題、圖例與繪圖區（線 mark／x 軸標籤）是否垂直重疊（不遮圖）、水平捲動、截圖。
const { chromium } = require('playwright');
const OUT = process.argv[2] || '.';
const PORT = process.env.PORT || 8571;
async function waitIdle(p, ms = 2500) {
  let quiet = 0;
  for (let i = 0; i < 240; i++) {
    const running = await p.evaluate(() => { const s = document.querySelector('[data-testid="stStatusWidget"]'); return !!(s && /Running|執行/.test(s.innerText || '')) || !!document.querySelector('[data-testid="stSpinner"]'); });
    quiet = running ? 0 : quiet + 250; if (quiet >= ms) return; await p.waitForTimeout(250);
  }
}
const PROBE = () => {
  const host = document.querySelector('.st-key-p4m_primary [data-testid="stVegaLiteChart"]');
  if (!host) return { chart: null };
  const hr = host.getBoundingClientRect();
  const rel = r => ({ x0: +(r.left - hr.left).toFixed(1), x1: +(r.right - hr.left).toFixed(1), y0: +(r.top - hr.top).toFixed(1), y1: +(r.bottom - hr.top).toFixed(1) });
  const labs = [...host.querySelectorAll('.role-legend-label text')];
  const syms = [...host.querySelectorAll('.role-legend-symbol path')];
  const entries = labs.map((t, i) => {
    const rs = [t.getBoundingClientRect(), syms[i] ? syms[i].getBoundingClientRect() : null].filter(r => r && r.width > 0);
    return { label: t.textContent, ...rel({ left: Math.min(...rs.map(r => r.left)), right: Math.max(...rs.map(r => r.right)), top: Math.min(...rs.map(r => r.top)), bottom: Math.max(...rs.map(r => r.bottom)) }) };
  });
  const title = [...host.querySelectorAll('.role-legend-title text')].map(e => e.textContent).join('');
  const titleBox = (() => { const e = host.querySelector('.role-legend-title'); return e ? rel(e.getBoundingClientRect()) : null; })();
  const lines = [...host.querySelectorAll('.role-mark.mark-line path, .mark-line path')].map(e => e.getBoundingClientRect());
  const xlab = [...host.querySelectorAll('.role-axis[aria-label*="X-axis"] text, .role-axis[aria-label*="x-axis"] text')].map(e => e.getBoundingClientRect());
  const yaxis = [...host.querySelectorAll('.role-axis[aria-label*="Y-axis"] text')].map(e => (e.textContent || '').trim());
  const plotBottom = Math.max(...lines.map(r => r.bottom), ...xlab.map(r => r.bottom), 0) - hr.top;
  const legTop = Math.min(...entries.map(e => e.y0), titleBox ? titleBox.y0 : 1e9);
  const sc = document.documentElement;
  return { chart: { w: +hr.width.toFixed(1), h: +hr.height.toFixed(1) }, title, titleBox, entries,
    allEntriesInsideWidth: entries.length > 0 && entries.every(e => e.x0 >= 0 && e.x1 <= hr.width + 0.5),
    maxRight: Math.max(...entries.map(e => e.x1)), minLeft: Math.min(...entries.map(e => e.x0)),
    legendTop: legTop, plotBottom: +plotBottom.toFixed(1), legendOverlapsPlot: legTop < plotBottom - 0.5,
    yAxisLabels: yaxis, hScroll: sc.scrollWidth > sc.clientWidth + 1, docScrollW: sc.scrollWidth, docClientW: sc.clientWidth };
};
(async () => {
  const b = await chromium.launch({ args: ['--no-sandbox'] });
  const res = {};
  for (const [state, q] of [['loaded', ''], ['report', '&report=1'], ['partial', '&report=partial'], ['cold', '&cold=1']]) {
    for (const [vn, w, h] of [['390', 390, 844], ['1440', 1440, 900]]) {
      const ctx = await b.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
      const p = await ctx.newPage();
      await p.goto(`http://localhost:${PORT}/?p=market${q}`, { waitUntil: 'networkidle' });
      await p.waitForSelector('text=📊 市場', { timeout: 90000 });
      await waitIdle(p); await p.waitForTimeout(1500);
      res[`${state}/${vn}`] = await p.evaluate(PROBE);
      const host = await p.$('.st-key-p4m_primary');
      if (host) { await host.scrollIntoViewIfNeeded(); await p.waitForTimeout(600); await host.screenshot({ path: `${OUT}/p4_5_primary_${state}_${vn}.png` }); }
      await ctx.close();
    }
  }
  console.log(JSON.stringify(res));
  await b.close();
})();
