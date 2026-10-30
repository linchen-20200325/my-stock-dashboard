// Phase 4 P4-1 QA 修正輪：L1 各「🔍 查看依據」展開後是否溢出所屬 tile（只量測，不改 app；不被 app／test import；開發用）
// 起因：QA 目視——手機打開位階 tile 的「🔍 查看依據」後，六欄內長 inline code 溢出蓋到水位 tile（scrollWidth 319 > 153）。
// 用法：NODE_PATH=/opt/node-tools/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//         node docs/vnext/phase4_market/p4_1/measure_p4_1_overflow.js <outdir>
// 判準：每個展開的 details 內，任一元素右緣 ≤ 所屬有框容器右緣＋1px，且 details 自身 scrollWidth ≤ clientWidth＋1。
const { chromium } = require('playwright');
const OUT = process.argv[2] || '.';
const PORT = process.env.PORT || 8571;

(async () => {
  const b = await chromium.launch({ args: ['--no-sandbox'] });
  const res = {};
  for (const [state, q] of [['loaded', ''], ['cold', '&cold=1']]) {
    for (const [vn, w, h] of [['1440', 1440, 900], ['390', 390, 844]]) {
      const ctx = await b.newContext({ viewport: { width: w, height: h } });
      const p = await ctx.newPage();
      await p.goto(`http://localhost:${PORT}/?p=market${q}`, { waitUntil: 'networkidle' });
      await p.waitForSelector('text=📊 市場', { timeout: 90000 });
      await p.waitForTimeout(4000);
      const n = await p.evaluate(() => document.querySelectorAll('.st-key-p4m_l1 [data-testid="stExpander"] summary').length);
      for (let i = 0; i < n; i++) {
        await p.evaluate((k) => { const s = document.querySelectorAll('.st-key-p4m_l1 [data-testid="stExpander"] summary')[k]; const d = s.closest('details'); if (d && !d.open) s.click(); }, i);
        await p.waitForTimeout(400);
      }
      await p.waitForTimeout(1500);
      res[`${state}/${vn}`] = await p.evaluate(() => [...document.querySelectorAll('.st-key-p4m_l1 [data-testid="stExpander"] details')].map(d => {
        const box = d.closest('[class*="st-key-p4m_box_"]') || d.closest('[data-testid="stForm"]') || d.closest('.st-key-p4m_l1');
        const br = box.getBoundingClientRect();
        let worst = 0, worstTag = '';
        for (const e of d.querySelectorAll('*')) {
          const r = e.getBoundingClientRect(); if (!r.width) continue;
          const over = r.right - br.right; if (over > worst) { worst = over; worstTag = e.tagName + ':' + (e.innerText || '').slice(0, 30); }
        }
        return { label: (d.querySelector('summary').innerText || '').trim().slice(0, 30), box: (box.className.match(/st-key-p4m_\w+/) || ['form'])[0],
                 overRightPx: Math.round(worst), worst: worstTag, scrollW: d.scrollWidth, clientW: d.clientWidth,
                 ok: worst <= 1 && d.scrollWidth <= d.clientWidth + 1 };
      }));
      if (state === 'loaded' && vn === '390') {
        await p.evaluate(() => { const t = document.querySelector('.st-key-p4m_box_regime'); if (t) t.scrollIntoView(); });
        await p.waitForTimeout(800);
        await p.screenshot({ path: `${OUT}/p4_1_overflow_regime_open_390.png` });
      }
      await ctx.close();
    }
  }
  console.log(JSON.stringify(res));
  await b.close();
})();
