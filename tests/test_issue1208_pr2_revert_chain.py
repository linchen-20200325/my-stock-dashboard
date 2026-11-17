"""tests/test_issue1208_pr2_revert_chain.py — Issue #1208 第二個 PR（MoneyDJ 全入口零請求止血，DEC-189）
的還原鏈新頭節。

═══ 為什麼需要 ═══════════════════════════════════════════════════════════
PR2 移除 PMI 競速 MoneyDJ 段（8→7 源）、更正 AI 問答來源字樣、教學表／R7-4 命中來源句「8 源」→「7 源」、
data_registry 兩筆 MoneyDJ 登錄等。這些檔被舊鏈（DEC-074／C1／C21／Z28／Z33／Z34／Z56／Z66b／UIM／XVEXT…）以
「新寫法 → 舊寫法」錨點還原成各自的基底 sha256；本批改動落在它們的比對範圍之內 ⇒ 在鏈頭**往前接一節**：
`i1208_revert_for`（PR1 頭節）開頭先呼叫本節的 `i1208pr2_revert_for`（比照 `twii_ohlc_revert_for` 開頭先呼叫
`i1208_revert_for` 的作法；⛔ 不動任何舊表與舊基底 sha、不放寬任何斷言、不 skip）。有意識的接鏈，不是漏改。

基底 ＝ PR2 開工前的 `b06a7eca`（origin/main，PR1 #1209 合併後）；`git show b06a7eca:<檔> | sha256sum` 實算後
寫死，測試不依賴 git。還原組由 difflib 逐區塊自動產生（每個 new 片段在現行檔恰 1 次、在基底 0 次）。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

I1208PR2_BASE_SHA = {'app.py': '8e7e7b14e8664cca6af6b646f4e17fb602010fed27dcfce93791b302f0f1d121',
 'scripts/probe_tw_sources.py': 'bd0d0ca4176f85f83942d0a11ef8a8e3aac99751daec1b803c72d2815167daaf',
 'shared/fetch_monitor.py': 'd9d288ee0da1021b197f7b8193fe6863a7324dcd7170a469c10a8f97f7bf61d1',
 'shared/schemas.py': '9ef382ec7683b2f97107c89274cdb71105e6b1557752e0d9747c701b0ceb68a1',
 'src/compute/etf/etf_calc.py': '5274ecb3a0d5982f5fb6d4588673d3028755e381cf265430eb700ac5594cbe14',
 'src/compute/etf/portfolio_gates.py': 'fed6857ad97d88abbe7758728f784bb45ad002bd1d9049e57a335c2c6d229bc4',
 'src/compute/macro/dated_inputs.py': '2ce460378d4ad2e24dacad0352877c380f4a15f579f1a953c75883b2c393dcd7',
 'src/compute/macro/macro_helpers.py': '5d99d8207846911521f26007733f64cb039f77da71b18d175c66bcfede6997fb',
 'src/data/core/data_registry.py': '0d0158b04ba1e74fd18827b42fd50caf4727df0981cfd8fe79277841d9a750ff',
 'src/data/macro/macro_core.py': 'be0e9a67fafd443f311cf5f74604564fc054237886c4b8e556cfe7955b2f757d',
 'src/data/macro/macro_snapshot.py': '5882d3f40be0ba151994e49fb646fa99778deceeb56aaefbf064a36b96baffb8',
 'src/data/macro/tw_macro.py': '7e441c0549dbef7a6c360978c2aa5e7ef80b49a9708cb3890f46e8af0bb7b1f6',
 'src/services/ai_qa_service.py': '1c707acd270dac35eab5cf7e2ba3dd657db2ad21deac0637aef77ee8629faba1',
 'src/ui/tabs/tab_edu.py': '5a382f83f1d08e4337109060b677115b6f1490b762da4f862947e5855b044caf'}

I1208PR2_REVERT_PAIRS = {'app.py': (('            #   render_data_health_raw 內另有未受 button 保護的 per-ETF 外抓(SITCA 等;#1208 PR2 起已無 '
             'MoneyDJ)。\n',
             '            #   render_data_health_raw 內另有未受 button 保護的 per-ETF 外抓(MoneyDJ/SITCA)。\n'),),
 'scripts/probe_tw_sources.py': (("        _verdict = ('🟡 STALE — 全段失敗,回的是 90 天內的舊快照' if _stale_flag\n",
                                  "        _verdict = ('🟡 STALE — 8 段全失敗,回的是 90 天內的舊快照' if _stale_flag\n"),),
 'shared/fetch_monitor.py': (('            `value=None` 診斷 dict」的**假綠燈**（如 `fetch_tw_pmi` 全源全敗仍回 dict\n',
                              '            `value=None` 診斷 dict」的**假綠燈**（如 `fetch_tw_pmi` 8 源全敗仍回 dict\n'),),
 'shared/schemas.py': (('    當期 TW PMI 由 `macro_core.fetch_tw_pmi`(多源賽跑;v19.113 起 8 源,#1208 PR2 起 7 '
                        '源)供應;PMISchema 保留供\n',
                        '    當期 TW PMI 由 `macro_core.fetch_tw_pmi`(8 源賽跑,v19.113)供應;PMISchema 保留供\n'),),
 'src/compute/etf/etf_calc.py': (('            # 繞過 Streamlit Cloud 美國 IP 對 TWSE/goodinfo 的 geo-block;TWSE '
                                  '折溢價\n',
                                  '            # 繞過 Streamlit Cloud 美國 IP 對 TWSE/goodinfo/MoneyDJ 的 '
                                  'geo-block;TWSE 折溢價\n'),
                                 ('                        # 假日/連假兜底：即時來源(goodinfo/TWSE)常只回一筆淨值，\n',
                                  '                        # 假日/連假兜底：即時來源(goodinfo/TWSE/MoneyDJ)常只回一筆淨值，\n'),
                                 ('      - 台灣 Yahoo：「台積電」（#1208 PR2 前 MoneyDJ 亦同格式，已移除）\n',
                                  '      - 台灣 Yahoo / MoneyDJ：「台積電」\n')),
 'src/compute/etf/portfolio_gates.py': (('    台股來源（台灣 Yahoo；#1208 PR2 前另有 MoneyDJ）回中文股名「台積電」；\n',
                                         '    台股來源（台灣 Yahoo / MoneyDJ）回中文股名「台積電」；\n'),),
 'src/compute/macro/dated_inputs.py': (('⚠️ 當期（live 多源賽跑或其 stale-cache）與前月（parquet 歷史）**可能來自不同來源** —— 兩者都在\n',
                                        '⚠️ 當期（live 8 源賽跑或其 stale-cache）與前月（parquet 歷史）**可能來自不同來源** —— '
                                        '兩者都在\n'),),
 'src/compute/macro/macro_helpers.py': (('        "ism_pmi":       _traced("ism_pmi", "台灣製造業 PMI（中華經濟研究院 '
                                         'CIER 等 7 源並行，依優先序取第一個有效值；全敗時沿用 90 天內舊值）", _g(macro_info, '
                                         '"ism_pmi", "value"), macro_info),\n',
                                         '        "ism_pmi":       _traced("ism_pmi", "台灣製造業 PMI（中華經濟研究院 '
                                         'CIER 等 8 源並行，依優先序取第一個有效值；全敗時沿用 90 天內舊值）", _g(macro_info, '
                                         '"ism_pmi", "value"), macro_info),\n'),),
 'src/data/core/data_registry.py': (("    {'category':'🇹🇼 台灣總經', 'name':'台灣製造業 PMI (CIER)', "
                                     "'source':'CIER-EN + data.gov.tw 6100 + 7 段並行',\n"
                                     "     'endpoint':'cier.edu.tw/en/eco (首選) / "
                                     'data.gov.tw/api/v2/rest/dataset/6100 / index.ndc / macromicro.me / '
                                     "stockfeel / cnyes',\n",
                                     "    {'category':'🇹🇼 台灣總經', 'name':'台灣製造業 PMI (CIER)', "
                                     "'source':'CIER-EN + data.gov.tw 6100 + 8 段並行',\n"
                                     "     'endpoint':'cier.edu.tw/en/eco (首選) / "
                                     'data.gov.tw/api/v2/rest/dataset/6100 / index.ndc / macromicro.me / '
                                     "stockfeel / cnyes / moneydj',\n"),
                                    ('    # Issue #1208 PR2（2026-11-17）：「MoneyDJ ETF '
                                     '基本資料」（Basic0004）與「基金淨值」\n'
                                     '    # （MoneyDJ YP010001）兩筆登錄已移除 —— MoneyDJ 全入口零請求止血，程式已無對應 caller。\n',
                                     "    {'category':'🏦 ETF / 基金', 'name':'MoneyDJ ETF 基本資料', "
                                     "'source':'MoneyDJ',\n"
                                     "     'endpoint':'moneydj.com/ETF/X/Basic/Basic0004.xdjhtm',\n"
                                     "     'identifier':'Basic0004',\n"
                                     "     'frequency':'event', 'requires_key':None,\n"
                                     "     'usage':'ETF 成分股、追蹤指數',\n"
                                     "     'state_key':None, 'pingable':False, 'ping_url':None},\n"
                                     "    {'category':'🏦 ETF / 基金', 'name':'基金淨值', 'source':'MoneyDJ',\n"
                                     "     'endpoint':'moneydj.com/funddj/yb/YP010001.djhtm',\n"
                                     "     'identifier':'YP010001',\n"
                                     "     'frequency':'daily', 'requires_key':None,\n"
                                     "     'usage':'基金淨值查詢',\n"
                                     "     'state_key':None, 'pingable':False, 'ping_url':None},\n")),
 'src/data/macro/macro_core.py': (('# v19.119：PMI 多源並行賽跑的**硬上限**（#1208 PR2 起 7 源,見 PMI_SOURCE_REGISTRY）。必須 < '
                                   'macro_trio_orchestrator 的\n',
                                   '# v19.119：PMI 8 源並行賽跑的**硬上限**。必須 < macro_trio_orchestrator 的\n'),
                                  ('# 備援順序：見檔末 PMI_SOURCE_REGISTRY(v19.113 起 8 源;#1208 PR2 移除 MoneyDJ 後 7 '
                                   '源;\n'
                                   '# 本註解原列 4 段為 v10 時代殘影,以 registry 為 SSOT 不再重複列舉)\n'
                                   '# ══════════════════════════════════════════════════════════════\n'
                                   '\n'
                                   "@monitored('fetch_tw_pmi', category='🇹🇼 台灣總經', frequency='monthly',\n"
                                   "           registry_key='🇹🇼 台灣 PMI 製造業指數',   # v19.96 批次4 Item1\n"
                                   '           # v19.118:治假綠燈——全源全敗仍回 dict(value=None)不拋例外,舊版恆綠誤導。\n'
                                   '           # 有值(含 durable stale 值)=綠;value=None(連 durable 都沒有)=紅。\n'
                                   '           success_check=lambda r: isinstance(r, dict) and '
                                   "r.get('value') is not None)\n"
                                   'def fetch_tw_pmi(*, max_age_days: int = 90) -> dict:\n'
                                   '    """抓取台灣製造業 PMI（多來源並行賽跑〔現 7 源，以 PMI_SOURCE_REGISTRY '
                                   '為準〕，依優先序取最高優先的有效值；月頻）。\n',
                                   '# 備援順序：見檔末 PMI_SOURCE_REGISTRY(v19.113 起 8 源;本註解原列 4 段為\n'
                                   '# v10 時代殘影,以 registry 為 SSOT 不再重複列舉)\n'
                                   '# ══════════════════════════════════════════════════════════════\n'
                                   '\n'
                                   "@monitored('fetch_tw_pmi', category='🇹🇼 台灣總經', frequency='monthly',\n"
                                   "           registry_key='🇹🇼 台灣 PMI 製造業指數',   # v19.96 批次4 Item1\n"
                                   '           # v19.118:治假綠燈——8 源全敗仍回 dict(value=None)不拋例外,舊版恆綠誤導。\n'
                                   '           # 有值(含 durable stale 值)=綠;value=None(連 durable 都沒有)=紅。\n'
                                   '           success_check=lambda r: isinstance(r, dict) and '
                                   "r.get('value') is not None)\n"
                                   'def fetch_tw_pmi(*, max_age_days: int = 90) -> dict:\n'
                                   '    """抓取台灣製造業 PMI（8 來源並行賽跑，依優先序取最高優先的有效值；月頻）。\n'),
                                  ('                → Cnyes → CIER(cid8)\n'
                                   '    (#1208 PR2 2026-11-17 拔除 MoneyDJ 段 — GPT 裁示 MoneyDJ 全入口零請求止血;\n'
                                   '    平行競速下即使前段命中仍會送出請求,故必須從 registry 移除而非降序。)\n',
                                   '                → Cnyes → CIER(cid8) → MoneyDJ\n'),
                                  ("            print(f'[macro_core/TW-PMI] ✅ 採用 {_nm}（{len(_sources)} "
                                   "源並行，依優先序）')\n"
                                   '            # v18.225 T1：命中即 snapshot 持久化，作為後續全失敗時的 stale fallback\n'
                                   "            _macro_cache_save('tw_pmi', _results[_nm])\n"
                                   '            # S-PROV-1 v18.254:provenance '
                                   'fetched_at(orchestrator-level)\n'
                                   '            _hit = dict(_results[_nm])\n'
                                   "            _hit['fetched_at'] = _fetched_at\n"
                                   '            return _hit\n'
                                   "    err_msg = ' | '.join(errs) or f'all {len(_sources)} stages failed'\n"
                                   "    print(f'[macro_core/TW-PMI] ❌ {len(_sources)} 段並行全失敗：{err_msg}')\n"
                                   '    # v18.225 T1：全段失敗 → 讀 stale cache（90 天 TTL），UI 端顯示 🟡 而非 🔴\n',
                                   "            print(f'[macro_core/TW-PMI] ✅ 採用 {_nm}（8 源並行，依優先序）')\n"
                                   '            # v18.225 T1：命中即 snapshot 持久化，作為後續全失敗時的 stale fallback\n'
                                   "            _macro_cache_save('tw_pmi', _results[_nm])\n"
                                   '            # S-PROV-1 v18.254:provenance '
                                   'fetched_at(orchestrator-level)\n'
                                   '            _hit = dict(_results[_nm])\n'
                                   "            _hit['fetched_at'] = _fetched_at\n"
                                   '            return _hit\n'
                                   "    err_msg = ' | '.join(errs) or 'all 8 stages failed'\n"
                                   "    print(f'[macro_core/TW-PMI] ❌ 8 段並行全失敗：{err_msg}')\n"
                                   '    # v18.225 T1：8 段全失敗 → 讀 stale cache（90 天 TTL），UI 端顯示 🟡 而非 🔴\n'),
                                  ('# Issue #1208 PR2（2026-11-17 GPT 裁示）：`_pmi_src_moneydj`（MoneyDJ '
                                   '財經知識庫搜尋頁）已移除。\n'
                                   '# MoneyDJ 權利未解決；平行競速下每次都會送出請求，故整段刪除（非降序）。\n',
                                   'def _pmi_src_moneydj(today, max_age_days, errs):\n'
                                   '    """方案 7: MoneyDJ 財經知識庫（搜尋頁，HTML 含 PMI 圖表 alt）。"""\n'
                                   '    try:\n'
                                   '        from bs4 import BeautifulSoup\n'
                                   '        mdj_url = '
                                   "('https://www.moneydj.com/KMDJ/Search/SearchListNew.aspx'\n"
                                   "                   '?keyword=%E5%8F%B0%E7%81%A3PMI&type=knowledge')\n"
                                   '        r = fetch_url(mdj_url, timeout=12, attempts=1)\n'
                                   '        if r is None:\n'
                                   "            errs.append('MoneyDJ:無回應')\n"
                                   '        else:\n'
                                   "            r.encoding = 'utf-8'\n"
                                   "            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', "
                                   'strip=True)\n'
                                   '            m = _re.search(\n'
                                   "                r'(20\\d{2})\\s*年\\s*(\\d{1,2})\\s*月.{0,40}?'\n"
                                   '                '
                                   "r'(?:台灣|TW)\\s*(?:製造業)?[^。]{0,40}?PMI[^。]{0,30}?(\\d{2}\\.\\d)',\n"
                                   '                txt)\n'
                                   '            if m:\n'
                                   '                yr, mo, v = m.group(1), int(m.group(2)), '
                                   'float(m.group(3))\n'
                                   '                if 30 <= v <= 70 and 1 <= mo <= 12:\n'
                                   '                    last_date = _dt.date(int(yr), mo, 1)\n'
                                   '                    if (today - last_date).days <= max_age_days:\n'
                                   "                        date = f'{yr}-{mo:02d}-01'\n"
                                   "                        print(f'[macro_core/TW-PMI/MoneyDJ] ✅ {v} "
                                   "date={date}')\n"
                                   "                        return {'value': v, 'date': date,\n"
                                   "                                'label': 'MoneyDJ 財經知識庫',\n"
                                   "                                'source': 'MoneyDJ', 'is_proxy': False,\n"
                                   "                                'series_id': 'mdj-tw-pmi'}\n"
                                   '            else:\n'
                                   "                errs.append('MoneyDJ:no-parse')   # v19.114:200 無 match "
                                   '原為靜默\n'
                                   '    except Exception as e:\n'
                                   "        errs.append(f'MoneyDJ:{type(e).__name__}')\n"
                                   "        print(f'[macro_core/TW-PMI/MoneyDJ] ❌ {e}')\n"
                                   '    return None\n'),
                                  ("    # ('MoneyDJ', _pmi_src_moneydj) — #1208 PR2 移除（MoneyDJ 全入口零請求止血）\n",
                                   "    ('MoneyDJ',     _pmi_src_moneydj),\n")),
 'src/data/macro/macro_snapshot.py': (('    """台灣 PMI(CIER 中華經濟研究院,委派 macro_core.fetch_tw_pmi 多源並行賽跑;#1208 '
                                       'PR2 起 7 源)。\n',
                                       '    """台灣 PMI(CIER 中華經濟研究院,委派 macro_core.fetch_tw_pmi 8 源並行賽跑)。\n'),
                                      ("    return {'_err_pmi': _result.get('_err_pmi', '7 源並行全失敗')}\n",
                                       "    return {'_err_pmi': _result.get('_err_pmi', '8 源並行全失敗')}\n")),
 'src/data/macro/tw_macro.py': (('# 當期 TW PMI 由 `fetch_tw_pmi`(macro_core,多源賽跑)供應,不需本死路徑。\n',
                                 '# 當期 TW PMI 由 `fetch_tw_pmi`(macro_core,8 源賽跑)供應,不需本死路徑。\n'),),
 'src/services/ai_qa_service.py': (('            # #1208 PR2（2026-11-17）：來源字樣對齊實際 '
                                    'caller（原「yfinance+SITCA」漏寫當時的第一順位\n'
                                    '            # MoneyDJ；MoneyDJ 移除後費用率鏈＝SITCA→元大(主動式)→yfinance）。文案待 '
                                    'ChatGPT 定稿。\n'
                                    '            "provenance": {"source": "ETF 品質(AUM規模/費用率/配息穩定度/beta;"\n'
                                    '                                     '
                                    '"AUM、Beta、配息＝yfinance；費用率＝SITCA→元大(主動式)→yfinance)",\n'
                                    '                           "as_of": None}}\n',
                                    '            "provenance": {"source": "ETF '
                                    '品質(AUM規模/費用率/配息穩定度/beta;yfinance+SITCA)", "as_of": None}}\n'),),
 'src/ui/tabs/tab_edu.py': (('#: ⓪ 資料來源地圖「🇹🇼 TW PMI」列的來源欄。\n'
                             '#: #1208 PR2（2026-11-17，DEC-189）：MoneyDJ 移出 PMI 競速 → 7 源；文案待 ChatGPT 定稿。\n'
                             '#: 抽成模組常數，讓舊批次「整頁 golden」測試可暫時換回修前原文\n'
                             '#: （tests/test_issue1208_pr2_revert_chain.py::i1208pr2_restore_edu_text；⛔ '
                             '不是洗掉本批改動）。\n'
                             "_TW_PMI_SOURCE_MAP_TEXT = '7 源賽跑：CIER-EN → data.gov.tw → NDC → CIER首頁 → "
                             "StockFeel → Cnyes → CIER-cid8'\n"
                             '\n'
                             '\n',
                             ''),
                            ('             _TW_PMI_SOURCE_MAP_TEXT,   # #1208 PR2：見模組常數註解\n',
                             "             '8 源賽跑：CIER-EN → data.gov.tw → NDC → CIER首頁 → StockFeel → Cnyes → "
                             "CIER-cid8 → MoneyDJ（v19.113）',\n"))}

#: `tab_edu._TW_PMI_SOURCE_MAP_TEXT` 的修前原文（b06a7eca 時是 `render_tab_edu` 內的字面值）。
_TW_PMI_SOURCE_MAP_TEXT_PRE_I1208PR2 = (
    '8 源賽跑：CIER-EN → data.gov.tw → NDC → CIER首頁 → StockFeel → Cnyes → CIER-cid8 → MoneyDJ（v19.113）')


def i1208pr2_restore_edu_text(mp) -> None:
    """舊批次「舊 UI 教學頁整頁 golden」比對用：把 #1208 PR2 改過的 TW PMI 來源欄暫時換回修前原文（monkeypatch）。

    由 `tests/test_dec074_revert_chain.py::dec074_restore_edu_text` 尾端呼叫（有意識的接鏈）；現行內容由
    `test_tw_pmi_source_map_text_is_current` 釘住 —— 這裡只為了讓守「別的事」的舊 golden 照舊逐字比對，
    ⛔ 不是洗掉本批的改動。
    """
    import src.ui.tabs.tab_edu as TE
    from src.data.macro import macro_core as MC
    mp.setattr(TE, "_TW_PMI_SOURCE_MAP_TEXT", _TW_PMI_SOURCE_MAP_TEXT_PRE_I1208PR2)
    # 原理教室的 §§PMI_SOURCES§§／§§PMI_SOURCE_COUNT§§ 由 registry「名稱」動態產生 ⇒ 名單也換回修前 8 源。
    # ⛔ 只換名單供文字渲染；第 8 源是 raise-if-called 的空殼，**絕不**發出任何請求。
    if [n for n, _f in MC.PMI_SOURCE_REGISTRY] == _PMI_NAMES_POST_I1208PR2:
        mp.setattr(MC, "PMI_SOURCE_REGISTRY",
                   list(MC.PMI_SOURCE_REGISTRY) + [("MoneyDJ", _inert_removed_pmi_source)])


#: PR2 後的 registry 名稱（只在完全相符時才補回第 8 源名稱，避免日後 registry 再變時默默蓋掉）。
_PMI_NAMES_POST_I1208PR2 = ["CIER-EN", "data.gov.tw", "NDC", "CIER", "StockFeel", "Cnyes", "CIER-cid8"]


def _inert_removed_pmi_source(*_a, **_k):
    raise AssertionError("#1208 PR2：MoneyDJ PMI 源已移除；本空殼僅供舊 golden 文字渲染，不得被呼叫")


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def i1208pr2_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 #1208 PR2 之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = I1208PR2_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} #1208 PR2 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_i1208pr2_revert_is_exact_base_source():
    assert set(I1208PR2_REVERT_PAIRS) == set(I1208PR2_BASE_SHA)
    for rel in sorted(I1208PR2_REVERT_PAIRS):
        code = i1208pr2_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == I1208PR2_BASE_SHA[rel], rel


def test_i1208pr2_revert_is_idempotent():
    for rel in sorted(I1208PR2_REVERT_PAIRS):
        once = i1208pr2_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert i1208pr2_revert_for(rel, once) == once, rel


def test_i1208pr2_link_is_reached_from_i1208_head():
    """接鏈本身：`i1208_revert_for`（PR1 頭節）必須先套本節，否則舊鏈對這些檔的基底 sha 會紅。"""
    from tests.test_issue1208_revert_chain import i1208_revert_for
    for rel in sorted(I1208PR2_REVERT_PAIRS):
        code = (REPO / rel).read_text(encoding="utf-8")
        assert i1208_revert_for(rel, code) == i1208pr2_revert_for(rel, code), rel


def test_tw_pmi_source_map_text_is_current():
    """現行教學地圖 TW PMI 來源欄：7 源、無 MoneyDJ（文案待 ChatGPT 定稿），且與 registry 數量一致。"""
    import src.ui.tabs.tab_edu as TE
    from src.data.macro.macro_core import PMI_SOURCE_REGISTRY
    assert TE._TW_PMI_SOURCE_MAP_TEXT == (
        '7 源賽跑：CIER-EN → data.gov.tw → NDC → CIER首頁 → StockFeel → Cnyes → CIER-cid8')
    assert TE._TW_PMI_SOURCE_MAP_TEXT.startswith(f'{len(PMI_SOURCE_REGISTRY)} 源')
    assert 'MoneyDJ' not in TE._TW_PMI_SOURCE_MAP_TEXT


def test_restore_helper_is_wired_into_dec074_restore():
    """接鏈本身：`dec074_restore_edu_text` 必須也換回本節的教學文字（否則舊整頁 golden 會紅）。"""
    import pytest
    import src.ui.tabs.tab_edu as TE
    from tests.test_dec074_revert_chain import dec074_restore_edu_text
    with pytest.MonkeyPatch.context() as mp:
        dec074_restore_edu_text(mp)
        assert TE._TW_PMI_SOURCE_MAP_TEXT == _TW_PMI_SOURCE_MAP_TEXT_PRE_I1208PR2
    assert TE._TW_PMI_SOURCE_MAP_TEXT != _TW_PMI_SOURCE_MAP_TEXT_PRE_I1208PR2
