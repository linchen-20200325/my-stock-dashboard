// 截圖＋量測 Phase 4 步驟 0 示意 HTML（1440x900／390x844）。用法：NODE_PATH=/opt/node-tools/node_modules node shoot_p4.js
const fs = require('fs'); const path = require('path');
const { chromium } = require('playwright');
const dir = __dirname;
(async () => {
  const b = await chromium.launch(process.env.PW_CHROME ? { executablePath: process.env.PW_CHROME, args: ['--no-sandbox'] } : {});
  const rep = {};
  for (const f of fs.readdirSync(dir).filter(n => n.endsWith('.html')).sort()) {
    const name = f.replace('.html', ''); const vn = name.endsWith('_390') ? '390' : '1440';
    const [w, h] = vn === '390' ? [390, 844] : [1440, 900];
    const ctx = await b.newContext({ viewport: { width: w, height: h } });
    const p = await ctx.newPage(); await p.goto('file://' + path.join(dir, f)); await p.waitForTimeout(150);
    await p.screenshot({ path: path.join(dir, name + '.png'), fullPage: true });
    rep[name] = await p.evaluate(() => {
      const r = {}; const top0 = (document.querySelector('#h2') || document.body).getBoundingClientRect().top;
      for (const id of ['h2', 'cta', 'concl', 'tiles', 'prim', 'a', 'b', 'b2', 'c']) {
        const e = document.getElementById(id); if (e) { const q = e.getBoundingClientRect(); r[id] = { y: Math.round(q.top), h: Math.round(q.height), bottom: Math.round(q.bottom) }; }
      }
      r.tileHeights = [...document.querySelectorAll('.cp-tile')].map(e => Math.round(e.getBoundingClientRect().height));
      r.overflowX = document.documentElement.scrollWidth > document.documentElement.clientWidth;
      r.docH = document.documentElement.scrollHeight; return r;
    });
    await ctx.close();
  }
  fs.writeFileSync(path.join(dir, '_measure.json'), JSON.stringify(rep, null, 1));
  console.log(JSON.stringify(rep));
  await b.close();
})();
