// Phase 4 P4-1：其他三頁與 `?legacy=1` 不受影響的實測（只量測，不改任何 app 檔；不被 app／test import；開發用）
// 用法：兩個 harness 同時在跑 —— 現行分支在 PORT_NEW（預設 8571），P4 開工前基底（git worktree @7484c57b）在 PORT_BASE（預設 8572）。
//   NODE_PATH=/opt/node-tools/node_modules PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//     node docs/vnext/phase4_market/p4_1/compare_other_pages.js <outdir>
// 比的是主內容區（stMain）＋側欄的可見文字（innerText）與 expander／按鈕標題；輸出 JSON（每個情境 same=true/false 與第一個差異）。
// 環境變數 ROOT_NEW／ROOT_BASE＝兩邊 repo 根目錄（traceback 路徑正規化用）。
const { chromium } = require('playwright');
const OUT = process.argv[2] || '.';
const NEW = process.env.PORT_NEW || 8571;
const BASE = process.env.PORT_BASE || 8572;
// 正規化：兩個 harness 的 repo 根目錄不同（例外 traceback 會印出路徑）、現在時刻不同 ⇒ 比對前一律換掉。
const ROOTS = [process.env.ROOT_NEW, process.env.ROOT_BASE].filter(Boolean);
const norm = t => ROOTS.reduce((a, r) => a.split(r).join('<ROOT>'), t).replace(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/g, '<NOW>');
const CASES = [
  ['target', 'p=target'], ['hold', 'p=hold'],
  ['legacy_market', 'p=market&legacy=1'], ['legacy_target', 'p=target&legacy=1'],
];

async function waitIdle(p, ms = 2500) {
  let quiet = 0;
  for (let i = 0; i < 240; i++) {
    const running = await p.evaluate(() => {
      const s = document.querySelector('[data-testid="stStatusWidget"]');
      return !!(s && /Running|執行/.test(s.innerText || '')) || !!document.querySelector('[data-testid="stSpinner"]');
    });
    quiet = running ? 0 : quiet + 250;
    if (quiet >= ms) return;
    await p.waitForTimeout(250);
  }
}

async function grab(b, port, q, w, h, shot) {
  const ctx = await b.newContext({ viewport: { width: w, height: h } });
  const p = await ctx.newPage();
  await p.goto(`http://localhost:${port}/?${q}`, { waitUntil: 'networkidle' });
  await p.waitForSelector('[data-testid="stMain"]', { timeout: 90000 });
  await p.waitForTimeout(1500);
  await waitIdle(p);
  const r = await p.evaluate(() => {
    const main = document.querySelector('[data-testid="stMain"]');
    const side = document.querySelector('[data-testid="stSidebar"]');
    const labels = [...document.querySelectorAll('summary, button')].map(e => (e.innerText || '').trim()).filter(Boolean);
    return { main: (main ? main.innerText : ''), side: (side ? side.innerText : ''), labels };
  });
  if (shot) await p.screenshot({ path: shot });
  await ctx.close();
  return r;
}

(async () => {
  const b = await chromium.launch({ args: ['--no-sandbox'] });
  const res = {};
  for (const [name, q] of CASES) {
    for (const [vn, w, h] of [['1440', 1440, 900], ['390', 390, 844]]) {
      const a = await grab(b, NEW, q, w, h, `${OUT}/other_${name}_${vn}.png`);
      const z = await grab(b, BASE, q, w, h, null);
      for (const o of [a, z]) { o.main = norm(o.main); o.side = norm(o.side); o.labels = o.labels.map(norm); }
      const same = a.main === z.main && a.side === z.side && JSON.stringify(a.labels) === JSON.stringify(z.labels);
      let diff = null;
      if (!same) {
        const al = a.main.split('\n'), zl = z.main.split('\n');
        const i = al.findIndex((l, k) => l !== zl[k]);
        diff = { line: i, now: (al[i] || '').slice(0, 80), base: (zl[i] || '').slice(0, 80), mainLen: [a.main.length, z.main.length] };
      }
      res[`${name}/${vn}`] = { same, mainChars: a.main.length, diff };
    }
  }
  console.log(JSON.stringify(res));
  await b.close();
})();
