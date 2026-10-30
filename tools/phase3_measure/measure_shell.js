// Phase 3 步驟 3：站殼間距量測（只量測，不改任何 app 檔；不被 app／test import）
// 用法：NODE_PATH=/opt/node-tools/node_modules node tools/phase3_measure/measure_shell.js http://localhost:8599
const { chromium } = require('playwright');
const BASE = process.argv[2] || 'http://localhost:8599';
const CHROME = process.env.PW_CHROME || '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome';

const PROBE = () => {
  const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect(); return { top: +b.top.toFixed(1), bottom: +b.bottom.toFixed(1), h: +b.height.toFixed(1), left: +b.left.toFixed(1), w: +b.width.toFixed(1) }; };
  const cs = (el, p) => el ? getComputedStyle(el)[p] : null;
  const q = (s) => document.querySelector(s);
  const main = q('[data-testid="stMainBlockContainer"]');
  const header = q('[data-testid="stHeader"]');
  // 站標帶：含「台股 AI 戰情室」且 font-size 22px 的 span 的外層 div
  const spans = [...document.querySelectorAll('span')].filter(s => s.textContent.includes('台股 AI 戰情室') && getComputedStyle(s).fontSize === '22px');
  const brand = spans[0] ? spans[0].parentElement : null;
  const brandMd = brand ? brand.closest('[data-testid="stElementContainer"]') : null;
  const hs = [...document.querySelectorAll('h1,h2,h3')].filter(h => h.getBoundingClientRect().height > 0);
  const h2 = hs.find(h => h.tagName === 'H2');
  const firstH = hs[0];
  // 主區內第一個非站標帶的元素容器
  const kids = main ? [...main.querySelectorAll('[data-testid="stElementContainer"]')] : [];
  const firstAfter = kids.find(k => k !== brandMd && k.getBoundingClientRect().height > 0 && !(brandMd && brandMd.contains(k)));
  const vh = window.innerHeight;
  // 第一屏可見內容：主區內所有 stElementContainer 與視窗 [0,vh] 的交集高度（排除站標帶本身）
  let vis = 0, brandVis = 0;
  kids.forEach(k => { const b = k.getBoundingClientRect(); const v = Math.max(0, Math.min(b.bottom, vh) - Math.max(b.top, 0)); if (k === brandMd) brandVis = v; else vis += v; });
  const bottomBar = q('[class*="st-key-nav4"]') ;
  return {
    viewport: { w: window.innerWidth, h: vh },
    stHeader: { rect: r(header), position: cs(header, 'position'), bg: cs(header, 'backgroundColor') },
    mainBlock: { rect: r(main), paddingTop: cs(main, 'paddingTop'), paddingBottom: cs(main, 'paddingBottom'), paddingLeft: cs(main, 'paddingLeft') },
    brandBand: { rect: r(brand), container: r(brandMd), paddingTop: cs(brand, 'paddingTop'), paddingBottom: cs(brand, 'paddingBottom'), fontSize: spans[0] ? cs(spans[0], 'fontSize') : null },
    firstElementAfterBrand: firstAfter ? { rect: r(firstAfter), text: firstAfter.innerText.slice(0, 40) } : null,
    firstHeading: firstH ? { tag: firstH.tagName, y: r(firstH).top, text: firstH.innerText.slice(0, 40) } : null,
    firstH2: h2 ? { y: r(h2).top, text: h2.innerText.slice(0, 40) } : null,
    allHeadings: hs.slice(0, 6).map(h => ({ tag: h.tagName, y: r(h).top, text: h.innerText.slice(0, 30) })),
    visibleContentPx: +vis.toFixed(1), brandVisiblePx: +brandVis.toFixed(1),
    visibleContentRatio: +(vis / vh).toFixed(3),
    docScrollHeight: document.documentElement.scrollHeight,
    sidebar: r(q('[data-testid="stSidebar"]')),
  };
};

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const out = {};
  for (const [name, w, h] of [['1440x900', 1440, 900], ['390x844', 390, 844]]) {
    for (const mode of ['nav4', 'legacy']) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h } });
      const page = await ctx.newPage();
      await page.goto(BASE + (mode === 'legacy' ? '/?legacy=1' : '/'), { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('[data-testid="stMainBlockContainer"]', { timeout: 60000 });
      await page.waitForTimeout(6000);
      out[`${name}/${mode}`] = await page.evaluate(PROBE);
      await page.screenshot({ path: `${process.env.OUT_DIR || '.'}/shell_${name}_${mode}.png` });
      await ctx.close();
    }
  }
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
