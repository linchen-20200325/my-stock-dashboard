// 以 page.addStyleTag 在瀏覽器內「假裝」套用候選 CSS，量 H2 y 可收多少 px（不改任何 repo 檔）
const { chromium } = require('playwright');
const BASE = process.argv[2] || 'http://localhost:8599';
const MAIN = '[data-testid="stMainBlockContainer"]';
const VB = MAIN + ' > [data-testid="stVerticalBlock"]';
const VARIANTS = {
  'V0 現況': '',
  'V1 padding-top 96→60px(=stHeader 高)': `${MAIN}{padding-top:60px !important}`,
  'V2 padding-top 96→72px': `${MAIN}{padding-top:72px !important}`,
  'V3 只收「零高度 style 容器」的 flex gap': `${VB} > [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style:only-child){display:none !important}`,
  'V4 V1+V3': `${MAIN}{padding-top:60px !important}${VB} > [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style:only-child){display:none !important}`,
  'V5 V4＋nav4 空 wrapper(桌機)隱藏': `${MAIN}{padding-top:60px !important}${VB} > [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style:only-child){display:none !important}@media (min-width:769px){${VB} > [data-testid="stLayoutWrapper"]:has(.st-key-nav4_bottom){display:none !important}}`,
};
(async () => {
  const b = await chromium.launch({ executablePath: process.env.PW_CHROME || '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome', args: ['--no-sandbox'] });
  const res = [];
  for (const [w,h] of [[1440,900],[390,844]]) for (const q of ['', '?legacy=1']) {
    const p = await (await b.newContext({ viewport: { width: w, height: h } })).newPage();
    await p.goto(BASE + '/' + q); await p.waitForSelector(MAIN); await p.waitForTimeout(6000);
    for (const [name, css] of Object.entries(VARIANTS)) {
      await p.evaluate(() => document.querySelectorAll('style[data-probe]').forEach(s => s.remove()));
      if (css) await p.evaluate((c) => { const s = document.createElement('style'); s.setAttribute('data-probe','1'); s.textContent = c; document.head.appendChild(s); }, css);
      await p.waitForTimeout(300);
      const m = await p.evaluate(() => {
        const brand = [...document.querySelectorAll('span')].find(s => s.textContent.includes('台股 AI 戰情室') && getComputedStyle(s).fontSize === '22px');
        const bt = brand ? brand.getBoundingClientRect().top : null;
        const h2 = [...document.querySelectorAll('h2')].find(e => e.getBoundingClientRect().height > 0);
        const firstTab = document.querySelector('.stTabs');
        return { brandTop: bt && +bt.toFixed(1), h2: h2 && +h2.getBoundingClientRect().top.toFixed(1), tabs: firstTab && +firstTab.getBoundingClientRect().top.toFixed(1) };
      });
      res.push({ vp: `${w}x${h}`, mode: q ? 'legacy' : 'nav4', variant: name, ...m });
    }
    await p.context().close();
  }
  console.table(res);
  await b.close();
})();
