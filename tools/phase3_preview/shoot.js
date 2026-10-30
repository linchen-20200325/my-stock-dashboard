// Playwright 截圖：1440x900 與 390x844（fullPage）。用法：node tools/phase3_preview/shoot.js
// 需要全域 playwright（NODE_PATH=/opt/node-tools/node_modules）與沙箱內既有 chromium（勿重裝）。
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PW_MODULE || '/opt/node-tools/node_modules/playwright');

const dir = path.resolve(__dirname, '../../docs/vnext/phase3_preview');
const VPS = [['1440', 1440, 900], ['390', 390, 844]];
const SKIP_MOBILE = new Set(['kpi_tile']);       // 手機改看 kpi_tile_m（2 欄示意）
const SKIP_DESKTOP = new Set(['kpi_tile_m']);
const ONLY_DESKTOP = new Set(['chips_light']);

(async () => {
  const browser = await chromium.launch();
  const report = {};
  for (const f of fs.readdirSync(dir).filter(n => n.endsWith('.html')).sort()) {
    const name = f.replace('.html', '');
    for (const [tag, w, h] of VPS) {
      if (tag === '390' && (SKIP_MOBILE.has(name))) continue;
      if (tag === '1440' && SKIP_DESKTOP.has(name)) continue;
      if (tag === '390' && ONLY_DESKTOP.has(name)) continue;
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      await page.goto('file://' + path.join(dir, f));
      await page.waitForTimeout(200);
      const out = path.join(dir, `${name}_${tag}.png`);
      await page.screenshot({ path: out, fullPage: true });
      // DOM 量測：橫向溢出、各元件尺寸
      const m = await page.evaluate(() => {
        const r = {};
        r.scrollW = document.documentElement.scrollWidth; r.clientW = document.documentElement.clientWidth;
        r.hOverflow = r.scrollW > r.clientW;
        const box = s => [...document.querySelectorAll(s)].map(e => { const b = e.getBoundingClientRect(); return [Math.round(b.width), Math.round(b.height)]; });
        document.querySelectorAll('.pv-row3,.pv-row2').forEach(e => e.style.alignItems = 'start');
        r.chipByFamily = {};
        for (const f of ['cp-info', 'cp-guard', 'cp-status']) { const a = box('.cp-chip.' + f); r.chipByFamily[f] = a.length ? [...new Set(a.map(x => x[1]))] : []; }
        r.tileNatural = [...document.querySelectorAll('.pv-row3,.pv-row2')].map(row => [...row.querySelectorAll('.cp-tile')].map(e => Math.round(e.getBoundingClientRect().height)));
        r.titleAttr = document.querySelectorAll('[title]').length;
        r.chip = box('.cp-chip').slice(0, 40);
        r.slotP = box('.cp-slot-primary'); r.slotL = box('.cp-slot-line');
        r.tile = box('.cp-tile'); r.spark = box('svg.cp-spark'); r.sparkMiss = box('.cp-spark-missing');
        r.smCell = box('.cp-sm-cell');
        // 子元素超出其容器的橫向溢出
        r.clipped = [...document.querySelectorAll('.cp-chip,.cp-tile,.cp-tile-value,.cp-sm-cell,.cp-slot,.cp-spark-missing')]
          .filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.className + ':' + e.textContent.slice(0, 20));
        r.fullH = document.documentElement.scrollHeight;
        return r;
      });
      report[`${name}_${tag}`] = m;
      await ctx.close();
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(dir, '_measure.json'), JSON.stringify(report, null, 1));
  console.log('done', Object.keys(report).length, 'shots');
})();
