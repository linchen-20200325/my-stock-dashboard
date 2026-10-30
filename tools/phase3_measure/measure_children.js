// 列出 stMainBlockContainer 第一層垂直子節點的 y／高／gap，找出「看不見但佔位」的元素
const { chromium } = require('playwright');
const BASE = process.argv[2] || 'http://localhost:8599';
(async () => {
  const b = await chromium.launch({ executablePath: process.env.PW_CHROME || '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome', args: ['--no-sandbox'] });
  for (const [w,h,q] of [[1440,900,''],[390,844,''],[1440,900,'?legacy=1']]) {
    const p = await (await b.newContext({ viewport: { width: w, height: h } })).newPage();
    await p.goto(BASE + '/' + q); await p.waitForSelector('[data-testid="stMainBlockContainer"]'); await p.waitForTimeout(6000);
    const rows = await p.evaluate(() => {
      const m = document.querySelector('[data-testid="stMainBlockContainer"]');
      const vb = m.firstElementChild; // stVerticalBlock
      const cs = getComputedStyle(vb);
      const kids = [...vb.children].slice(0, 9).map(k => { const r = k.getBoundingClientRect(); return { tid: k.getAttribute('data-testid'), cls: k.className.toString().slice(0,40), y: +r.top.toFixed(1), h: +r.height.toFixed(1), txt: k.innerText.slice(0, 24).replace(/\n/g,' '), hasStyle: !!k.querySelector('style') }; });
      return { gap: cs.rowGap, kids };
    });
    console.log(w, q || 'nav4', JSON.stringify(rows, null, 0));
    await p.context().close();
  }
  await b.close();
})();
