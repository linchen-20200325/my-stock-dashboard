// Phase 4 步驟 0：📊 市場頁現況量測（只量測，不改任何 app 檔；不被 app／test import；開發用）
// 用法（repo 根目錄；harness 已在 PORT，預設 8571）：
//   NODE_PATH=/opt/node-tools/node_modules node docs/vnext/phase4_market/baseline/measure_market.js <outdir>
// 輸出：JSON 到 stdout；截圖 <outdir>/p4m_<state>_<1440|390>.png（第一屏）。state = loaded | cold | report
const { chromium } = require('playwright');
const OUT = process.argv[2] || '.';
const PORT = process.env.PORT || 8571;
const CHROME = process.env.PW_CHROME || undefined;

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

const PROBE = (vh) => {
  const sc = [document.querySelector('[data-testid="stMain"]'), document.querySelector('[data-testid="stAppViewContainer"]'), document.scrollingElement]
    .find(e => e && e.scrollHeight > e.clientHeight + 5 && getComputedStyle(e).overflowY !== 'visible') || document.scrollingElement;
  const st = sc.scrollTop || 0;
  const main = document.querySelector('[data-testid="stMainBlockContainer"]');
  const abs = el => { const r = el.getBoundingClientRect(); return { y: Math.round(r.top + st), h: Math.round(r.height), x: Math.round(r.left), w: Math.round(r.width) }; };
  const hidden = el => { const r = el.getBoundingClientRect(); if (r.height === 0 || r.width === 0) return true; const d = el.closest('details'); return !!(d && !d.open && !el.closest('summary')); };
  const txt = el => (el.innerText || '').replace(/\s+/g, '').length;
  const h2 = [...main.querySelectorAll('h2')].find(h => /市場/.test(h.innerText));
  const h2y = h2 ? abs(h2).y : null;
  // 找包含文字的最小可見元素（markdown／容器）
  const findText = (re) => { const els = [...main.querySelectorAll('[data-testid="stMarkdownContainer"], [data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"], button')].filter(e => !hidden(e) && re.test(e.innerText || '')); els.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length); return els[0] || null; };
  const probeText = (name, re) => { const e = findText(re); return { name, found: !!e, ...(e ? abs(e) : {}), relH2: e && h2y !== null ? abs(e).y - h2y : null, inFirstScreen: e ? abs(e).y < vh : false }; };
  const targets = [
    probeText('今日結論句', /市場位階：.*台股趨勢：/),
    probeText('今日結論標題', /今日結論（五項各自判斷/),
    probeText('更新鈕', /🚀 更新今日戰情/),
    probeText('⚡ 需要處理', /^⚡ 需要處理/),
    probeText('圖A', /^圖A/),
    probeText('圖B', /^圖B/),
    probeText('圖C', /^圖C/),
    probeText('圖D', /^圖D/),
  ];
  // Hero 4 卡：主區內第一組 stHorizontalBlock 的子欄
  const rows = [...main.querySelectorAll('[data-testid="stHorizontalBlock"]')].filter(e => !hidden(e)).map(e => ({ ...abs(e), cols: [...e.children].filter(c => !hidden(c)).map(c => ({ ...abs(c), head: (c.innerText || '').split('\n')[0].slice(0, 20) })) }));
  const charts = [...main.querySelectorAll('[data-testid="stVegaLiteChart"]')].filter(e => !hidden(e)).map(e => abs(e));
  const titles = [...main.querySelectorAll('[title]')].filter(e => !hidden(e) && e.getAttribute('title')).map(e => ({ title: e.getAttribute('title').slice(0, 40), tag: e.tagName, text: (e.innerText || '').slice(0, 20) }));
  const expanders = [...main.querySelectorAll('[data-testid="stExpander"]')].filter(e => !hidden(e)).map(e => ({ ...abs(e), label: ((e.querySelector('summary') || e).innerText || '').replace(/keyboard_arrow_\w+/g, '').trim().split('\n')[0].slice(0, 40), open: !!(e.querySelector('details') || {}).open }));
  const text = main.innerText || '';
  const cnt = re => (text.match(re) || []).length;
  // 第一屏可見字數：與 [0,vh] 有交集的 stElementContainer 內文字（粗估）
  let fsChars = 0;
  [...main.querySelectorAll('[data-testid="stElementContainer"]')].filter(e => !hidden(e)).forEach(e => { const r = abs(e); if (r.y < vh && !e.querySelector('[data-testid="stElementContainer"]')) fsChars += txt(e); });
  return {
    h2y, scrollH: sc.scrollHeight, vh,
    targets, rows: rows.slice(0, 6), charts, titles, expanders,
    counts: { missingGlyph_blank: cnt(/⬜/g), unavailable_words: cnt(/無法判定|尚未|未評估|無資料|不足/g), totalChars: txt(main) },
    firstScreenChars: fsChars,
  };
};

(async () => {
  const b = await chromium.launch(CHROME ? { executablePath: CHROME, args: ['--no-sandbox'] } : {});
  const res = {};
  for (const [state, q] of [['loaded', ''], ['cold', '&cold=1'], ['report', '&report=1']]) {
    for (const [vn, w, h] of [['1440', 1440, 900], ['390', 390, 844]]) {
      const ctx = await b.newContext({ viewport: { width: w, height: h } });
      const p = await ctx.newPage();
      await p.goto(`http://localhost:${PORT}/?p=market${q}`, { waitUntil: 'networkidle' });
      await p.waitForSelector('text=📊 市場', { timeout: 90000 });
      await waitIdle(p);
      await p.evaluate(() => { for (const e of [document.querySelector('[data-testid="stMain"]'), document.querySelector('[data-testid="stAppViewContainer"]'), document.scrollingElement]) if (e) e.scrollTop = 0; });
      await p.waitForTimeout(1200);
      await p.screenshot({ path: `${OUT}/p4m_${state}_${vn}.png` });
      res[`${state}/${vn}`] = await p.evaluate(PROBE, h);
      await ctx.close();
    }
  }
  console.log(JSON.stringify(res));
  await b.close();
})();
