// 用法: NODE_PATH=<global node_modules> PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node pw_measure.js http://localhost:8561
const { chromium } = require('playwright');
const url = process.argv[2];
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true, isMobile: true });
  const p = await ctx.newPage();
  await p.goto(url); await p.waitForSelector('.st-key-seg5 button', { timeout: 30000 });
  await p.waitForTimeout(1500);
  const runs = async () => (await p.locator('text=/RUNS=\\d+/').first().innerText());
  const txt = async (re) => (await p.locator(`text=/${re}/`).first().innerText());
  console.log('version check: ', await p.evaluate(() => window.__streamlit?.BACKEND_BASE_URL ?? 'n/a'));
  const widgets = await p.evaluate(() => {
    const out = [];
    const docW = document.documentElement.scrollWidth, vw = window.innerWidth;
    for (const key of ['seg5', 'seg5long', 'seg3', 'pills5', 'radio5', 'fseg', 'fradio']) {
      const el = document.querySelector('.st-key-' + key); if (!el) { out.push({ key, missing: true }); continue; }
      const r = el.getBoundingClientRect();
      const btns = [...el.querySelectorAll('button, label')].filter(x => x.getBoundingClientRect().width > 0);
      const rows = new Set(btns.map(x => Math.round(x.getBoundingClientRect().top)));
      out.push({ key, x: Math.round(r.x), w: Math.round(r.width), right: Math.round(r.right), scrollW: el.scrollWidth, clientW: el.clientWidth,
        nItems: btns.length, rows: rows.size,
        items: btns.map(x => { const q = x.getBoundingClientRect(); return [x.innerText.trim(), 'w' + Math.round(q.width), 'h' + Math.round(q.height), 'L' + Math.round(q.left), 'R' + Math.round(q.right)]; }) });
    }
    return { docW, vw, out };
  });
  console.log('docScrollWidth', widgets.docW, 'viewport', widgets.vw);
  for (const w of widgets.out) console.log(JSON.stringify(w));
  // overflow: any item right > viewport
  // Interaction: click a segmented item (outside form) and check rerun
  const before = await runs();
  await p.locator('.st-key-seg5').getByRole('button',{name:'近3月',exact:true}).click();
  await p.waitForTimeout(1200);
  console.log('outside-form click: runs', before, '->', await runs(), '|', await txt('SEG5=.*'));
  // deselect by clicking the selected one again
  await p.locator('.st-key-seg5').getByRole('button',{name:'近3月',exact:true}).click();
  await p.waitForTimeout(1200);
  console.log('click selected again (deselect): ', await txt('SEG5=.*'), '| runs', await runs());
  // radio / pills
  await p.locator('.st-key-pills5').getByRole('button',{name:'近6月',exact:true}).click(); await p.waitForTimeout(1000);
  console.log('pills click:', await txt('PILLS=.*'));
  await p.locator('.st-key-pills5').getByRole('button',{name:'近6月',exact:true}).click(); await p.waitForTimeout(1000);
  console.log('pills deselect:', await txt('PILLS=.*'));
  // tap via touchscreen on segmented item
  const bb = await p.locator('.st-key-seg3').getByRole('button',{name:'月',exact:true}).boundingBox();
  await p.touchscreen.tap(bb.x + bb.width / 2, bb.y + bb.height / 2); await p.waitForTimeout(1000);
  console.log('touch tap seg3 月:', await txt('SEG3=.*'));
  // form
  await p.locator('.st-key-fseg').getByRole('button',{name:'近6月',exact:true}).scrollIntoViewIfNeeded();
  const r0 = await runs();
  await p.locator('.st-key-fseg').getByRole('button',{name:'近6月',exact:true}).click();
  await p.waitForTimeout(1200);
  console.log('in-form click: runs', r0, '->', await runs(), '| FORM line:', await txt('FORM sub=.*'));
  await p.locator('.st-key-fseg').getByRole('button',{name:'近6月',exact:true}).click(); // deselect in form
  await p.waitForTimeout(500);
  await p.getByRole('button', { name: '套用' }).click(); await p.waitForTimeout(1500);
  console.log('after submit w/ deselected: ', await txt('FORM sub=.*'), '| runs', await runs());
  await p.locator('.st-key-fseg').getByRole('button',{name:'全部',exact:true}).click();
  await p.getByRole('button', { name: '套用' }).click(); await p.waitForTimeout(1500);
  console.log('after select 全部 + submit: ', await txt('FORM sub=.*'));
  // keep value across unrelated rerun: click expander (no rerun) skip; check persisted after another widget change
  console.log('SEG5 after other widget interactions:', await txt('SEG5=.*'));
  // other APIs presence
  const other = await p.evaluate(() => ({
    badge: !!document.querySelector('[data-testid="stBadge"]'),
    html: !!document.querySelector('#htmlbox'), htmlSvg: !!document.querySelector('#htmlbox svg'),
    metricChart: document.querySelectorAll('[data-testid="stMetricChart"]').length,
    metrics: document.querySelectorAll('[data-testid="stMetric"]').length,
    charts: document.querySelectorAll('[data-testid="stVegaLiteChart"]').length,
    expanderIcon: !!document.querySelector('[data-testid="stExpander"] [data-testid="stExpanderIcon"]'),
    containerScroll: (() => { const c = [...document.querySelectorAll('[data-testid="stVerticalBlock"]')].find(e => e.scrollHeight > e.clientHeight + 5 && e.clientHeight >= 100 && e.clientHeight <= 140); return c ? [c.clientHeight, c.scrollHeight] : null; })(),
    exceptions: document.querySelectorAll('[data-testid="stException"]').length,
  }));
  console.log('other', JSON.stringify(other));
  await p.screenshot({ path: process.argv[3] || 'shot.png', fullPage: true });
  await b.close();
})();
