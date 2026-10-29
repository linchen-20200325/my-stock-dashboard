// Visual Fidelity 量測（開發工具）：計算 📊 市場／💼 持股可見文字（收合中的 expander 不算）裡工程字樣出現次數。
// 用法：node count_eng_words.js   （需 harness 已在 PORT，預設 8571）
const {chromium}=require('playwright');
const PORT=process.env.PORT||8571;
(async()=>{const b=await chromium.launch();const W=['線框','SSOT','digest','expander','widget','Gate','C2b','unwired','session','L0','L2','L3','L4','L5','warroom','eps_high','judged_count','鐵律'];
for(const [pg,ex] of [['market','&report=1'],['hold','']]){const p=await b.newPage({viewport:{width:1440,height:900}});await p.goto('http://localhost:'+PORT+'/?p='+pg+ex,{waitUntil:'networkidle'});await p.waitForTimeout(9000);
const r=await p.evaluate((W)=>{const main=document.querySelector('[data-testid="stMainBlockContainer"]');let t='';const tw=document.createTreeWalker(main,NodeFilter.SHOW_TEXT);let n;while((n=tw.nextNode())){const pe=n.parentElement;if(!pe||pe.getBoundingClientRect().height===0)continue;const d=pe.closest('details');if(d&&!d.open&&!pe.closest('summary'))continue;t+=n.textContent+' ';}
const o={};for(const w of W){const c=t.split(w).length-1;if(c)o[w]=c;}return o;},W);console.log(pg,JSON.stringify(r));await p.close();}
await b.close();})();
