const { chromium } = require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:390,height:844}});
await p.goto('http://localhost:'+process.argv[2]);await p.waitForSelector('.st-key-seg button',{timeout:30000});await p.waitForTimeout(1200);
const t=async()=>[await p.locator('text=/EFF=.*/').innerText(), await p.evaluate(()=>[...document.querySelectorAll('.st-key-seg button[data-testid$="Active"]')].map(x=>x.innerText))];
console.log('init',await t());
const btn=n=>p.locator('.st-key-seg').getByRole('button',{name:n,exact:true});
await btn('c').click();await p.waitForTimeout(1000);console.log('click c',await t());
await btn('c').click();await p.waitForTimeout(1200);console.log('click c again (deselect)',await t());
await p.locator('.st-key-fseg').getByRole('button',{name:'a',exact:true}).click();
await p.getByRole('button',{name:'go'}).click();await p.waitForTimeout(1000);console.log(await p.locator('text=/APPLIED=.*/').innerText());
await p.locator('.st-key-fseg').getByRole('button',{name:'a',exact:true}).click();
await p.getByRole('button',{name:'go'}).click();await p.waitForTimeout(1000);console.log('form deselect+submit ->',await p.locator('text=/APPLIED=.*/').innerText());
await b.close()})()
