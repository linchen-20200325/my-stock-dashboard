// Visual Fidelity 量測（開發工具）：blueprint 第一屏墨水比例（與 measure_app.js 同一格點算法，6px 格）。
// 用法：node mock_ink.js
const path=require('path');
const {chromium}=require('playwright');
const MOCK=path.resolve(__dirname,'..','..','docs','vnext','d25_wireframes')+'/';
(async()=>{const b=await chromium.launch();const out={};
for(const pg of ['market','target','holdings'])for(const [vn,w,h,view] of [['1440',1440,900,'desktop'],['390',390,844,'phone']]){
const p=await b.newPage({viewport:{width:w,height:h}});await p.goto('file://'+MOCK+pg+'.html');
await p.evaluate(v=>{document.body.dataset.view=v},view);await p.waitForTimeout(200);
out[pg+'_'+vn]=await p.evaluate((vh)=>{const root=document.querySelector(document.body.dataset.view==='desktop'?'.desk .main':'.phone .scr');
const rr=root.getBoundingClientRect();const x0=rr.left,x1=rr.right,y0=Math.max(0,rr.top),y1=Math.min(vh,rr.bottom);const cell=6;
const gw=Math.ceil((x1-x0)/cell),gh=Math.ceil((y1-y0)/cell);const g=new Uint8Array(gw*gh);
const mark=r=>{const a=Math.max(0,Math.floor((r.left-x0)/cell)),bb=Math.min(gw-1,Math.floor((r.right-x0)/cell)),c=Math.max(0,Math.floor((r.top-y0)/cell)),d=Math.min(gh-1,Math.floor((r.bottom-y0)/cell));for(let j=c;j<=d;j++)for(let i=a;i<=bb;i++)g[j*gw+i]=1;};
const tw=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let n;while((n=tw.nextNode())){if(!n.textContent.trim())continue;const pe=n.parentElement;if(!pe||pe.getBoundingClientRect().height===0)continue;const d=pe.closest('details');if(d&&!d.open&&!pe.closest('summary'))continue;const rg=document.createRange();rg.selectNodeContents(n);for(const r of rg.getClientRects())if(r.bottom>y0&&r.top<y1)mark(r);}
for(const e of root.querySelectorAll('svg,button,input,canvas,img')){const r=e.getBoundingClientRect();if(r.height&&r.bottom>y0&&r.top<y1)mark(r);}
let s=0;for(const v of g)s+=v;return {ink:+(s/g.length).toFixed(3),region:[Math.round(y0),Math.round(y1)]};},h);await p.close();}
console.log(JSON.stringify(out));await b.close();})();
