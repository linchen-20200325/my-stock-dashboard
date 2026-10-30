// Phase 3 站殼間距 D7=B 施工驗證：四頁 × 兩視窗，量 H2 y／第一個可見內容 y／padding／側欄與底部列樣式／layout jump／legacy。
// 用法：TAG=before|after [STRIP_RULES=1] [LOAD=1] OUT_DIR=docs/vnext/phase3_shell NODE_PATH=/opt/node-tools/node_modules node tools/phase3_measure/measure_shell_fix.js http://localhost:8599
//   STRIP_RULES=1：載入後把「站殼間距兩條規則」從 DOM 的 <style> 文字剔除（模擬 :has()／selector 失效），量是否回到現況。
//   LOAD=1：每頁嘗試點擊第一個非導覽的 button（loaded state；點不到就如實記錄）。
const { chromium } = require('playwright');
const BASE = process.argv[2] || 'http://localhost:8599';
const TAG = process.env.TAG || 'run';
const OUT = process.env.OUT_DIR || '.';
const CHROME = process.env.PW_CHROME || '/opt/pw-browsers/chromium-1243/chrome-linux64/chrome';
const PAGES = [['market', '📊 市場'], ['target', '🎯 標的'], ['holding', '💼 持股'], ['mine', '👤 我的']];
const VPS = [['1440x900', 1440, 900], ['390x844', 390, 844]];
const MAIN = '[data-testid="stMainBlockContainer"]';

const PROBE = () => {
  const r = (el) => { if (!el) return null; const b = el.getBoundingClientRect(); return { top: +b.top.toFixed(2), h: +b.height.toFixed(2), left: +b.left.toFixed(2), w: +b.width.toFixed(2) }; };
  const cs = (el, p) => el ? getComputedStyle(el)[p] : null;
  const q = (s) => document.querySelector(s);
  const main = q('[data-testid="stMainBlockContainer"]');
  const brandSpan = [...document.querySelectorAll('span')].find(s => s.textContent.includes('台股 AI 戰情室') && getComputedStyle(s).fontSize === '22px');
  const brand = brandSpan ? brandSpan.parentElement : null;
  const brandC = brand ? brand.closest('[data-testid="stElementContainer"]') : null;
  const h2 = [...document.querySelectorAll('h2')].find(e => e.getBoundingClientRect().height > 0);
  const kids = main ? [...main.querySelectorAll(':scope > [data-testid="stVerticalBlock"] > *')] : [];
  const vis = kids.filter(k => k.getBoundingClientRect().height > 0 && k !== brandC);
  const hiddenKids = kids.filter(k => getComputedStyle(k).display === 'none');
  const visText = (k) => { const c = k.cloneNode(true); c.querySelectorAll('style,script').forEach(x => x.remove()); return (c.textContent || '').trim(); };
  const hiddenWithText = hiddenKids.filter(k => visText(k).length > 0).map(k => visText(k).slice(0, 60));
  const hiddenNotStyleOnly = hiddenKids.filter(k => visText(k).length > 0 || !k.querySelector('style')).length;
  const side = q('[data-testid="stSidebar"]');
  const bar = q('.st-key-nav4_bottom');
  const firstTab = q('.stTabs');
  return {
    paddingTop: cs(main, 'paddingTop'), paddingBottom: cs(main, 'paddingBottom'),
    brandTop: brandSpan ? +brandSpan.getBoundingClientRect().top.toFixed(2) : null,
    h2Y: h2 ? +h2.getBoundingClientRect().top.toFixed(2) : null, h2Text: h2 ? h2.innerText.slice(0, 20) : null,
    firstVisibleContentY: vis[0] ? +vis[0].getBoundingClientRect().top.toFixed(2) : null,
    firstVisibleContentText: vis[0] ? (vis[0].innerText || '').trim().slice(0, 24) : null,
    tabsTop: firstTab ? +firstTab.getBoundingClientRect().top.toFixed(2) : null,
    hiddenTopLevelCount: hiddenKids.length, hiddenWithText, hiddenNotStyleOnly,
    sidebarBg: cs(side, 'backgroundColor'), sidebarColor: cs(side, 'color'), sidebarW: side ? +side.getBoundingClientRect().width.toFixed(1) : null,
    barPos: cs(bar, 'position'), barDisplay: cs(bar, 'display'), barBg: cs(bar, 'backgroundColor'), barColor: cs(bar, 'color'), barRect: r(bar),
    barBorderTop: cs(bar, 'borderTopColor'),
    scrollH: document.documentElement.scrollHeight, scrollW: document.documentElement.scrollWidth, innerW: window.innerWidth,
  };
};

async function gotoPage(page, vp, label) {
  const sel = vp.w <= 768 ? `.st-key-nav4_bottom label:has-text("${label}")` : `[data-testid="stSidebar"] label:has-text("${label}")`;
  if (label !== '📊 市場') { await page.locator(sel).first().click(); }
  await page.waitForTimeout(5000);
}

(async () => {
  const browser = await chromium.launch({ executablePath: CHROME, args: ['--no-sandbox'] });
  const out = {};
  const H2Y = () => { const e = [...document.querySelectorAll('h2')].find(x => x.getBoundingClientRect().height > 0); return e ? +e.getBoundingClientRect().top.toFixed(1) : null; };
  const top = (page) => page.evaluate(() => { window.scrollTo(0, 0); document.querySelectorAll('section, [data-testid="stMain"], [data-testid="stAppViewContainer"]').forEach(e => { e.scrollTop = 0; }); });
  for (const [vn, w, h] of VPS) {
    for (const [pid, label] of PAGES) {   // 每頁一個全新 context（cold 不受其他頁 session 污染）
      const ctx = await browser.newContext({ viewport: { width: w, height: h } });
      const page = await ctx.newPage();
      const errs = []; page.on('pageerror', e => errs.push(String(e).slice(0, 200)));
      await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector(MAIN, { timeout: 60000 });
      const series0 = [];
      for (let i = 0; i < 30; i++) { series0.push(await page.evaluate(H2Y)); await page.waitForTimeout(150); }
      await page.waitForTimeout(3000);
      if (process.env.STRIP_RULES) {
        const n = await page.evaluate(() => { let c = 0; document.querySelectorAll('style').forEach(s => { const t = s.textContent; if (t.includes('padding-top:72px') || t.includes('style:only-child')) { s.textContent = t.split('\n').filter(l => !(l.includes('padding-top:72px') || l.includes('style:only-child'))).join('\n'); c++; } }); return c; });
        out[`${vn}/${pid}/stripped_style_tags`] = n; await page.waitForTimeout(500);
      }
      const series = [];
      if (label !== '📊 市場') {
        const sel = w <= 768 ? `.st-key-nav4_bottom label:has-text("${label}")` : `[data-testid="stSidebar"] label:has-text("${label}")`;
        await page.locator(sel).first().click();
        for (let i = 0; i < 40; i++) { series.push(await page.evaluate(() => { const e = [...document.querySelectorAll('h2')].find(x => x.getBoundingClientRect().height > 0); const f = document.querySelector('[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > *:nth-child(n+6)'); return e ? +e.getBoundingClientRect().top.toFixed(1) : 'noH2'; })); await page.waitForTimeout(150); }
      } else series.push(...series0);
      await page.waitForTimeout(2000);
      out[`${vn}/nav4/${pid}/h2_series_compact`] = series.filter((v, i, a) => i === 0 || v !== a[i - 1]);
      await top(page);
      out[`${vn}/nav4/${pid}/cold`] = await page.evaluate(PROBE);
      await page.screenshot({ path: `${OUT}/${pid}_${vn}_${TAG}_cold.png` });
      if (process.env.LOAD) {
        const b = page.locator(`${MAIN} button`).filter({ hasText: /載入|更新今日|開始選股|生成/ }).first();
        if (await b.count()) {
          out[`${vn}/nav4/${pid}/load_button`] = (await b.innerText()).slice(0, 20);
          await b.click(); await page.waitForTimeout(9000); await top(page);
          out[`${vn}/nav4/${pid}/loaded`] = await page.evaluate(PROBE);
          await page.screenshot({ path: `${OUT}/${pid}_${vn}_${TAG}_loaded.png` });
        } else out[`${vn}/nav4/${pid}/loaded`] = 'NO_LOAD_BUTTON_FOUND';
      }
      out[`${vn}/${pid}/pageerrors`] = errs;
      await ctx.close();
    }
    // legacy
    const c2 = await browser.newContext({ viewport: { width: w, height: h } });
    const p2 = await c2.newPage();
    await p2.goto(BASE + '/?legacy=1', { waitUntil: 'domcontentloaded' });
    await p2.waitForSelector(MAIN, { timeout: 60000 }); await p2.waitForTimeout(7000);
    out[`${vn}/legacy`] = await p2.evaluate(PROBE);
    await p2.screenshot({ path: `${OUT}/legacy_${vn}_${TAG}.png` });
    await c2.close();
  }
  console.log(JSON.stringify(out, null, 1));
  await browser.close();
})();
