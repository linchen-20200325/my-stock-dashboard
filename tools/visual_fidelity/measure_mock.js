// Visual Fidelity 量測（開發工具）：渲染已核准 blueprint（docs/vnext/d25_wireframes/{market,target,holdings}.html）
// 的桌機框（1440×900）與手機框（390×844），量區塊／卡片／svg／表格／CTA 位置並截第一屏。
// 用法：node measure_mock.js <outdir>   （y 座標相對於 mockup 框 .desk .main／.phone .scr）
const path = require('path');
const {chromium} = require('playwright');
const OUT = process.argv[2];
const MOCK = path.resolve(__dirname, '..', '..', 'docs', 'vnext', 'd25_wireframes') + '/';
(async () => {
  const b = await chromium.launch();
  const res = {};
  for (const page of ['market', 'target', 'holdings']) {
    res[page] = {};
    for (const [vname, w, h, view] of [['1440', 1440, 900, 'desktop'], ['390', 390, 844, 'phone']]) {
      const p = await b.newPage({viewport: {width: w, height: h}});
      await p.goto('file://' + MOCK + page + '.html');
      await p.evaluate(v => { document.body.dataset.view = v; }, view);
      await p.waitForTimeout(300);
      const m = await p.evaluate((view) => {
        const root = view === 'desktop' ? document.querySelector('.desk .main') : document.querySelector('.phone .scr');
        const r0 = root.getBoundingClientRect();
        const top0 = r0.top - root.scrollTop;
        const rel = el => { const r = el.getBoundingClientRect(); return {y: Math.round(r.top - top0), h: Math.round(r.height), w: Math.round(r.width)}; };
        const vis = el => { const r = el.getBoundingClientRect(); if (r.height === 0) return false; let e = el; while (e && e !== root) { if (e.tagName === 'DETAILS' && !e.open && !e.contains(document.activeElement)) { const s = e.querySelector('summary'); if (s && !s.contains(el) && el !== s) return false; } e = e.parentElement; } return true; };
        const txt = el => (el.innerText || '').replace(/\s+/g, '').length;
        const blocks = [];
        // walk children; expand wrapper divs that only wrap
        const walk = (el, depth) => {
          for (const c of el.children) {
            if (!vis(c)) continue;
            const cls = c.className && typeof c.className === 'string' ? c.className : '';
            const isWrap = (c.tagName === 'DIV' && !cls && c.children.length >= 1 && depth < 3);
            if (isWrap && c.children.length > 1) { walk(c, depth + 1); continue; }
            const g = rel(c);
            const charts = [...c.querySelectorAll('.chart svg, svg')].filter(vis).map(s => Math.round(s.getBoundingClientRect().height));
            const cards = [...c.querySelectorAll('.card')].filter(vis).length + (cls.includes('card') ? 1 : 0);
            const head = (c.querySelector('h2,h3,h4,.sec,summary') || c).innerText.split('\n')[0].slice(0, 50);
            blocks.push({tag: c.tagName.toLowerCase(), cls: cls.slice(0, 30), ...g, chars: txt(c), cards, charts, head});
          }
        };
        walk(root, 0);
        const allCards = [...root.querySelectorAll('.card')].filter(vis).map(c => ({...rel(c), chars: txt(c), head: (c.querySelector('h3,h4') || c).innerText.split('\n')[0].slice(0, 40)}));
        const svgs = [...root.querySelectorAll('svg')].filter(vis).map(s => ({...rel(s)}));
        const tables = [...root.querySelectorAll('table')].filter(vis).map(t => ({...rel(t), rows: t.querySelectorAll('tr').length}));
        const details = [...root.querySelectorAll('details')].filter(d => vis(d)).map(d => ({...rel(d), label: d.querySelector('summary').innerText.slice(0, 40)}));
        const ctas = [...root.querySelectorAll('button, .cta, .btn2')].filter(vis).map(x => ({...rel(x), t: x.innerText.slice(0, 30)}));
        return {contentH: root.scrollHeight, frameTop: Math.round(r0.top), blocks, allCards, svgs, tables, details, ctas,
                totalChars: txt(root)};
      }, view);
      res[page][vname] = m;
      // screenshots: viewport (first screen) and a tall one
      await p.screenshot({path: `${OUT}/mock_${page}_${vname}.png`});
      await p.close();
    }
  }
  console.log(JSON.stringify(res, null, 1));
  await b.close();
})();
