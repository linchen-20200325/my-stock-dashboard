// layout jump 取樣：頁面載入起每個 rAF 記錄「站標 top／第一個 H2 top」的變化，輸出變化序列（比較前後是否多出新的位移）。
// 用法：NODE_PATH=/opt/node-tools/node_modules node tools/phase3_measure/measure_jump.js http://localhost:8599 [runs]
const { chromium } = require('playwright');
const BASE = process.argv[2] || 'http://localhost:8599'; const RUNS = +(process.argv[3] || 3);
const CHROME = process.env.PW_CHROME || '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome';
(async () => {
  const b = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  for (const [w, h] of [[1440, 900], [390, 844]]) for (let r = 0; r < RUNS; r++) {
    const ctx = await b.newContext({ viewport: { width: w, height: h } });
    await ctx.addInitScript(() => {
      window.__j = []; let last = '';
      const f = () => {
        const bs = [...document.querySelectorAll('span')].find(s => s.textContent.includes('台股 AI 戰情室') && getComputedStyle(s).fontSize === '22px');
        const h2 = [...document.querySelectorAll('h2')].find(e => e.getBoundingClientRect().height > 0);
        const v = `${bs ? Math.round(bs.getBoundingClientRect().top) : '-'}|${h2 ? Math.round(h2.getBoundingClientRect().top) : '-'}`;
        if (v !== last) { window.__j.push([Math.round(performance.now()), v]); last = v; }
        requestAnimationFrame(f);
      }; requestAnimationFrame(f);
    });
    const p = await ctx.newPage();
    await p.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
    await p.waitForSelector('[data-testid="stMainBlockContainer"]', { timeout: 60000 }); await p.waitForTimeout(7000);
    console.log(`${w}x${h} run${r}:`, JSON.stringify((await p.evaluate(() => window.__j)).map(x => x[1])));
    await ctx.close();
  }
  await b.close();
})();
