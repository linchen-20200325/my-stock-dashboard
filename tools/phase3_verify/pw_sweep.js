// 寬度掃描 + 點擊高度 CSS 覆寫。用法: node pw_sweep.js <port8561 app> <port8563 app>
const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();
for (const [port, keys] of [[process.argv[2], ['seg5','seg5long','seg3','pills5','fseg']],[process.argv[3], ['seg5','fseg']]]) {
 console.log('== app port', port);
 for (const w of [320,360,390,412]) {
  const p=await b.newPage({viewport:{width:w,height:800},hasTouch:true,isMobile:true});
  await p.goto('http://localhost:'+port);await p.waitForSelector('.st-key-seg5 button',{timeout:30000});await p.waitForTimeout(1200);
  const r=await p.evaluate((keys)=>{const o={docW:document.documentElement.scrollWidth,vw:innerWidth};
   for(const k of keys){const el=document.querySelector('.st-key-'+k);if(!el){continue}
    const bs=[...el.querySelectorAll('button')].filter(x=>x.getBoundingClientRect().width>0);
    const tops=new Set(bs.map(x=>Math.round(x.getBoundingClientRect().top)));
    const maxR=Math.max(...bs.map(x=>x.getBoundingClientRect().right));
    o[k]={rows:tops.size,h:Math.round(bs[0].getBoundingClientRect().height),minW:Math.round(Math.min(...bs.map(x=>x.getBoundingClientRect().width))),maxRight:Math.round(maxR)}}
   return o},keys);
  console.log(w, JSON.stringify(r));
  await p.close();}
}
await b.close()})()
