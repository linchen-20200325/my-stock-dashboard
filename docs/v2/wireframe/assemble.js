global.window = { WF_PAGES: [], WF_DECISIONS: [], WF_DEVIATIONS: [], WF_LIMITS: [] };
const FILES = ['./wf_page_today.js','./wf_page_find.js','./wf_page_inspect.js',
               './wf_page_hold.js','./wf_page_why.js','./wf_page_fund.js','./wf_global.js','./wf_questions.js'];
for (const f of FILES) { try { require(f); } catch (e) { console.error('LOAD FAIL', f, e.message); process.exit(1); } }
const W = global.window;

// 機械正規化：有些組直接給 blocks 沒給 layers（契約偏差），包一層，不動內容
for (const p of W.WF_PAGES) {
  if (!p.layers && Array.isArray(p.blocks)) {
    p.layers = [{ n: 0, label: p.title || '（不分層）', blocks: p.blocks }];
    delete p.blocks;
  }
  p.layers = p.layers || [];
  p.leaves = p.leaves || [];
  for (const l of p.layers) l.blocks = l.blocks || [];
}
const ORDER = ['today','find','inspect','hold','why','fund','rebalance','global'];
W.WF_PAGES.sort((a,b) => {
  const ia = ORDER.indexOf(a.id), ib = ORDER.indexOf(b.id);
  return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
});

// 契約健檢（只回報，不修改內容）
const KEYS = ['live','idle','loading','empty','missing','na','partial','degraded','unwired','error'];
let warn = [], totalBlocks = 0, seen = new Set();
for (const p of W.WF_PAGES) for (const l of p.layers) for (const b of l.blocks) {
  totalBlocks++;
  if (seen.has(b.key)) { b.key = p.id + '::' + b.key; }
  if (seen.has(b.key)) warn.push(`仍重複 key: ${b.key}`);
  seen.add(b.key);
  const miss = KEYS.filter(k => !(k in (b.states || {})));
  if (miss.length) warn.push(`${b.key} 缺狀態: ${miss.join(',')}`);
  if (!b.cols) warn.push(`${b.key} 無 cols`);
}
const out = [
  '/* ==== 線框資料（七組各自產出，總管機械組裝，內容未經改寫）==== */',
  'window.WF_PAGES.push.apply(window.WF_PAGES, ' + JSON.stringify(W.WF_PAGES) + ');',
  'window.WF_DECISIONS.push.apply(window.WF_DECISIONS, ' + JSON.stringify(W.WF_DECISIONS) + ');',
  'window.WF_DEVIATIONS.push.apply(window.WF_DEVIATIONS, ' + JSON.stringify(W.WF_DEVIATIONS) + ');',
  'window.WF_LIMITS.push.apply(window.WF_LIMITS, ' + JSON.stringify(W.WF_LIMITS) + ');',
].join('\n');
require('fs').writeFileSync('_wf_bundle.js', out);
console.log('頁面:', W.WF_PAGES.map(p => `${p.id}(${p.layers.reduce((a,l)=>a+l.blocks.length,0)})`).join(' '));
console.log(`區塊合計 ${totalBlocks}｜決策 ${W.WF_DECISIONS.length}｜偏離 ${W.WF_DEVIATIONS.length}｜限制 ${W.WF_LIMITS.length}`);
console.log(warn.length ? '⚠️ 契約警告 ' + warn.length + ' 條:\n  ' + warn.slice(0,8).join('\n  ') : '✅ 契約健檢全過');
