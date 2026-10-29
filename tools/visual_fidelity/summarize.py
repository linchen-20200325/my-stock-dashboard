"""Visual Fidelity 量測（開發工具）：把 measure_app.js 的 JSON 彙整成文字摘要。

用法：python3 tools/visual_fidelity/summarize.py app_market.json
"""
import json
import sys

with open(sys.argv[1], encoding="utf-8") as _f:
    d = json.load(_f)
for vp,m in d.items():
    vh=900 if vp=='1440' else 844
    print('=====',vp,'scrollH',m['scrollH'],'mainTop',m['mainTop'],'mainX',m['mainX'],'mainW',m['mainW'],'sidebarW',m['sidebarW'],'bottomNav',m['bottomNav'],'ink',m['inkRatioFirst'],'vcov',m['vertCoverFirst'],'chars',m['totalVisibleChars'],'errors',m['errors'][:3])
    for o in m['outline']:
        print(f"  y{o['y']:5} h{o['h']:5} w{o['w']:5} chars{o['chars']:5} charts{o['charts']} {o['kind']} | {o['t'][:60]}")
    print(' charts',[(c['y'],c['h'],c['w']) for c in m['charts']])
    print(' dfs',[(x['y'],x['h'],x['rows']) for x in m['dfs']],' tables',[(t['y'],t['h'],t['rows'],t['cls'][:12]) for t in m['tables']])
    print(' expanders',len(m['expanders']),[(e['y'],e['label'][:22]) for e in m['expanders']][:40])
    print(' borders',len(m['borders']),'firstscreen',sum(1 for b in m['borders'] if b['y']<vh))
    print(' htmlcards',len(m['htmlCards']),[(c['y'],c['h'],c['chars'],c['head'][:20]) for c in m['htmlCards']][:30])
    print(' buttons',[(b['y'],b['t'][:18]) for b in m['buttons']][:30])
    fs=[l for l in m['leaves'] if l['y']<vh]
    print(' firstscreen leaves',len(fs),'chars',sum(l['chars'] for l in fs))
    txt=[l for l in m['leaves'] if l['kind'] in('stMarkdown','stCaptionContainer','stMarkdownContainer','stText','stAlert') ]
    print(' text leaves',len(txt),'chars',sum(l['chars'] for l in txt),' long(>80):',sum(1 for l in txt if l['chars']>80))
