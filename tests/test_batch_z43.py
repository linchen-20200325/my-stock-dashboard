"""批 Z43：板塊產業別改依官方產業代碼選列＋同義板塊標準化合併（客戶 Q-z29＝A）。

客戶裁示（硬約束）
------------------
- (1) 上櫃「金融業」併入「金融保險」；(2) 上市 ETF 與上櫃 ETF 合併為同一個 ETF 泡泡。
- 資料層保留原始交易所／原始產業名稱／來源，不覆寫；名稱標準化在標準化（呈現前）層完成，可追溯。
- 只合併經官方定義或實際成分確認為同義者；「電子工業」「化學生技醫療」先證明是取法 bug 才修，不自行重分類。
- 合併前後：板塊數、成分股數、外資／投信／自營商金額守恆；缺值不得補 0；不新增可見字句、不改版面。

官方證據（GitHub runner 探針第 7 輪 run 38191149822）
---------------------------------------------------
- 上市 openapi `t187ap03_L`（`公司代號`、`產業別`＝兩位數代碼，1095 筆）、上櫃 `mopsfin_t187ap03_O`
  （`SecuritiesCompanyCode`、`SecuritiesIndustryCode`，893 筆），共用同一代碼體系。
- FinMind TaiwanStockInfo 4333 列／3154 檔、1055 檔多列；例 2344 華邦電兩列（'半導體業'、'電子工業'，
  date 同為 2026-10-11）、2308 台達電兩列（'電子工業' 在前、'電子零組件業' 在後）—— 舊碼取第一列 ⇒ 取錯。
- 00679B 兩列：'上櫃指數股票型基金(ETF)' date 2024-12-30、'上櫃ETF' date 2026-10-11。

突變：`Z43_REVERT_PAIRS` 為本批兩個被鎖定檔「修後逐字 → 修前（基底 `7c1adf8a`）逐字」（difflib 由實檔產生、
round-trip 驗過），還原體 sha256 ＝ 基底實檔；Z39／Z41／Z42 的還原鏈已串接本表。
"""
from __future__ import annotations

import copy
import functools
import hashlib
import importlib.util
import json
import math
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_CLOSE = "src/data/stock/market_close_fetcher.py"
_L0 = "shared/sector_flow_thresholds.py"
_L2 = "src/compute/sector_flow.py"
_SCRIPT = "scripts/update_sector_flow.py"

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原 / 突變 infra
# ══════════════════════════════════════════════════════════════════════════
#: 本批被鎖定兩檔：修後逐字 → 基底 `7c1adf8a` 逐字（difflib 由實檔產生、round-trip 驗過）。
Z43_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _CLOSE: (
        ('2. ticker → **產業別**對照:\n   - `fetch_industry_map_bulk()` : 批 Z43(客戶 Q-z29＝A)起依**官方產業別代碼**選列 ——\n     FinMind `TaiwanStockInfo` 整表原始列(不帶 data_id;每檔可多列)+ 官方 openapi\n     TWSE `t187ap03_L`(上市)/ TPEx `mopsfin_t187ap03_O`(上櫃)的產業別代碼(T1 免 token),\n     規則見 `select_industry_records`;完整選列紀錄由 `get_last_industry_raw()` 交 cron 落地。\n\n',
         '2. ticker → **產業別**對照:\n   - `fetch_industry_map_bulk()` : FinMind `TaiwanStockInfo` 整表(不帶 data_id;\n     非時間序列,理論不受 date-bulk gate)為主 → TWSE `t187ap03_L` + TPEX `t187ap03_O`\n     官方 openapi(T1 免 token)補齊仍缺者。\n\n'),
        ('# ══════════════════════════════════════════════════════════════════════\n#: 批 Z43(客戶 Q-z29＝A):官方「公司基本資料」openapi(產業別欄＝兩位數**代碼**;代碼 ↔ 名稱 SSOT\n#: 見 `shared.industry_codes`)。GitHub runner 探針第 7 輪 run 38191149822 實測:上市 1095 筆、上櫃 893 筆。\n#: ⚠️ 上櫃舊 URL `openapi.twse.com.tw/v1/opendata/t187ap03_O` 回 HTML(JSONDecodeError)—— 舊備援從未生效。\nTWSE_COMPANY_INFO_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"\nTPEX_COMPANY_INFO_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"\nMARKET_TWSE = "上市"\nMARKET_TPEX = "上櫃"\n#: (市場, 端點, 代號欄, 產業別代碼欄) —— 欄名**完全相等**定位(探針原文),找不到 → 該市場不可用(⛔ 不猜欄)。\n_OFFICIAL_INDUSTRY_SOURCES: tuple[tuple[str, str, str, str], ...] = (\n    (MARKET_TWSE, TWSE_COMPANY_INFO_URL, "公司代號", "產業別"),\n    (MARKET_TPEX, TPEX_COMPANY_INFO_URL, "SecuritiesCompanyCode", "SecuritiesIndustryCode"),\n)\n#: FinMind `TaiwanStockInfo` 的 `type` 欄 → 市場(用來判斷「官方查無」的代號是否屬於本次官方失敗的市場)。\n_FINMIND_TYPE_MARKET = {"twse": MARKET_TWSE, "tpex": MARKET_TPEX}\n\n',
         '# ══════════════════════════════════════════════════════════════════════\ndef _finmind_industry_map(token: str) -> dict:\n    """FinMind TaiwanStockInfo 整表(不帶 data_id)→ {code: industry_category}。\n\n'),
        ('\n#: 選列規則(寫進 industry_raw 每檔 `chosen.rule`;決定論、可追溯)。\nRULE_OFFICIAL_MATCH = "official_match_finmind"   # FinMind 某列 ＝ 官方名(完全或去尾「業/類」)→ 用該列 FinMind 名\nRULE_OFFICIAL_NAME = "official_name"             # 官方有產業別、FinMind 無任何列相符 → 用官方名\nRULE_NO_OFFICIAL = "finmind_no_official"         # 官方查無 / 官方名空白 / 未知代碼 → FinMind 決定論\nRULE_OFFICIAL_UNAVAILABLE = "official_unavailable"  # 該代號所屬市場官方端點本次失敗\n\n#: 最近一次 `fetch_industry_map_bulk()` 的完整選列紀錄(原始列 + 官方 + chosen);cron 落地 industry_raw 用。\n_LAST_INDUSTRY_RAW: dict = {}\n\n\ndef _finmind_industry_rows(token: str) -> list[dict] | None:\n    """FinMind TaiwanStockInfo 整表(不帶 data_id)→ 原始列 list(**不去重、不丟 type/date**)。\n\n    憑證只走 header(不進 query string,對齊 §資安慣例)。失敗/被 gate → None(與「0 列」區分)。\n    批 Z43:改回傳原始列;舊版「每檔取第一個非空列」(列順序不固定、多列 date 常相同 → 約 6 成多列股取錯)\n    已移除,選列改由 `select_industry_records` 依官方產業代碼決定。\n    """\n',
         '\n    憑證只走 header(不進 query string,對齊 §資安慣例)。回空 = 失敗/被 gate。\n    """\n'),
        ('            print(f"[industry/FinMind] HTTP={r.status_code} body={r.text[:160]}")\n            return None\n        d = r.json()\n',
         '            print(f"[industry/FinMind] HTTP={r.status_code} body={r.text[:160]}")\n            return {}\n        d = r.json()\n'),
        ('                  f"msg={d.get(\'msg\', \'\')}")\n            return None\n        rows = [x for x in (d.get("data") or []) if isinstance(x, dict)]\n        print(f"[industry/FinMind] TaiwanStockInfo: {len(rows)} 列 / "\n              f"{len({str(x.get(\'stock_id\', \'\')).strip() for x in rows})} 檔")\n        return rows\n    except Exception as e:\n',
         '                  f"msg={d.get(\'msg\', \'\')}")\n            return {}\n        out: dict = {}\n        for row in d.get("data", []) or []:\n            code = str(row.get("stock_id", "")).strip()\n            ind = str(row.get("industry_category", "")).strip()\n            if code and ind and code not in out:\n                out[code] = ind\n        print(f"[industry/FinMind] TaiwanStockInfo: {len(out)} 檔")\n        return out\n    except Exception as e:\n'),
        ('        print(f"[industry/FinMind] ❌ {type(e).__name__}: {e}")\n        return None\n\n',
         '        print(f"[industry/FinMind] ❌ {type(e).__name__}: {e}")\n        return {}\n\n'),
        ('\ndef _official_industry_codes() -> tuple[dict, dict]:\n    """官方 openapi(上市 t187ap03_L + 上櫃 mopsfin_t187ap03_O)→ ({代號: {market, code, endpoint}}, 狀態)。\n\n',
         '\ndef _openapi_industry_map() -> dict:\n    """TWSE t187ap03_L(上市)+ TPEX t187ap03_O(上櫃)官方 openapi → {code: 產業別}。\n\n'),
        ('\n    狀態 = {市場: {"ok": bool, "n": int, "reason": str|None, "endpoint": url}}。\n    某市場非 200 / 非 JSON / 非 list / 0 筆 / 欄名找不到 / 0 檔可解析 → ok=False(§1 不猜、不靜默退回)。\n    同代號兩市場皆出現(轉市場過渡)→ 先到者(上市)為準並 log。\n    走 `_fetch`(fetch_url:NAS→直連降級、失敗間隔退避、只快取 200)。\n    """\n',
         '\n    T1 免 token 備援(FinMind 被 gate 時用)。欄名容錯:公司代號/Code、產業別/\n    Industry。回空 = 全失敗。\n    """\n'),
        ('    out: dict = {}\n    status: dict = {}\n    for market, url, k_code, k_ind in _OFFICIAL_INDUSTRY_SOURCES:\n        st = {"ok": False, "n": 0, "reason": None, "endpoint": url}\n        status[market] = st\n        try:\n',
         '    out: dict = {}\n    sources = [\n        "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",\n        "https://openapi.twse.com.tw/v1/opendata/t187ap03_O",\n    ]\n    for url in sources:\n        try:\n'),
        ('        try:\n            r = _fetch(url, timeout=20)\n            if r is None or getattr(r, "status_code", 0) != 200:\n',
         '        try:\n            r = _fetch(url, timeout=15)\n            if r is None or getattr(r, "status_code", 0) != 200:\n'),
        ('            if r is None or getattr(r, "status_code", 0) != 200:\n                st["reason"] = f"HTTP={getattr(r, \'status_code\', \'None\')}"\n                print(f"[industry/official] {market} {st[\'reason\']} {url}")\n                continue\n',
         '            if r is None or getattr(r, "status_code", 0) != 200:\n                print(f"[industry/openapi] {url.split(\'/\')[-1]} "\n                      f"HTTP={getattr(r, \'status_code\', \'None\')}")\n                continue\n'),
        ('                continue\n            try:\n                data = r.json()\n            except ValueError as e:\n                st["reason"] = f"非 JSON:{type(e).__name__}"\n                print(f"[industry/official] {market} {st[\'reason\']} body[:200]="\n                      f"{scrubbed_body_head(r)[:200]!r}")\n                continue\n',
         '                continue\n            data = r.json()\n            if not isinstance(data, list):\n                continue\n'),
        ('                continue\n            if not isinstance(data, list) or not data:\n                st["reason"] = f"非 list 或 0 筆({type(data).__name__})"\n                print(f"[industry/official] {market} {st[\'reason\']}")\n                continue\n            if not isinstance(data[0], dict) or k_code not in data[0] or k_ind not in data[0]:\n                _keys = list(data[0].keys()) if isinstance(data[0], dict) else type(data[0]).__name__\n                st["reason"] = f"欄名找不到 {k_code!r}/{k_ind!r}:{_keys}"\n                print(f"[industry/official] {market} {st[\'reason\']}")\n                continue\n            n = 0\n            for item in data:\n',
         '                continue\n            before = len(out)\n            for item in data:\n'),
        ('            for item in data:\n                if not isinstance(item, dict):\n                    continue\n                code = str(item.get(k_code, "")).strip()\n                ind = str(item.get(k_ind, "")).strip()\n                if not code or not ind:\n                    continue\n                n += 1\n                if code in out:\n                    print(f"[industry/official] ⚠️ {code} 同時出現於 {out[code][\'market\']} 與 {market}"\n                          f" → 以 {out[code][\'market\']} 為準")\n                    continue\n                out[code] = {"market": market, "code": ind, "endpoint": url}\n            st["n"] = n\n            if n == 0:\n                st["reason"] = "0 檔可解析(代號或產業別代碼皆空)"\n                print(f"[industry/official] {market} {st[\'reason\']}")\n                continue\n            st["ok"] = True\n            print(f"[industry/official] {market}:{n} 檔")\n        except Exception as e:\n',
         '            for item in data:\n                code = str(item.get("公司代號", item.get("Code", ""))).strip()\n                ind = str(item.get("產業別",\n                                   item.get("Industry",\n                                            item.get("industry_category", "")))\n                          ).strip()\n                if code and ind and code not in out:\n                    out[code] = ind\n            print(f"[industry/openapi] {url.split(\'/\')[-1]}: +{len(out) - before} 檔")\n        except Exception as e:\n'),
        ('        except Exception as e:\n            st["reason"] = f"{type(e).__name__}: {e}"\n            print(f"[industry/official] {market} ❌ {st[\'reason\']}")\n    return out, status\n\n\ndef _finmind_deterministic(labels_dates: list[tuple[str, str]]) -> str | None:\n    """[(label, date)] → date 最新者;同 date 取名稱字典序最小(決定論、與 API 列順序無關)。空 → None。"""\n    xs = [(lab, str(dt or "")) for lab, dt in labels_dates if lab]\n    if not xs:\n        return None\n    _latest = max(dt for _, dt in xs)\n    return min(lab for lab, dt in xs if dt == _latest)\n\n\ndef select_industry_records(finmind_rows, official: dict, *,\n                            unavailable_markets=()) -> dict:\n    """純函式:FinMind 原始列 + 官方 {代號: {market, code, endpoint}} → {代號: 選列紀錄}。\n\n    每檔規則(批 Z43,決定論):\n      1. 官方代碼 → 官方名稱(`shared.industry_codes`)。\n      2. FinMind 某列與官方名「完全相同」或「去尾『業/類』後相同」→ 用該列 **FinMind 名**\n         (`official_match_finmind`;多列皆符取完全相同者,否則 date 最新、名稱字典序)。\n      3. 官方有產業名但 FinMind 無任何列相符 → 用**官方名**(`official_name`)。\n      4. 官方查無 / 官方名空白(\'91\' TDR)/ 未知代碼 → FinMind 決定論(`finmind_no_official`)。\n      5. 官方查無且該檔 FinMind `type` 屬於本次官方失敗的市場 → FinMind 決定論、rule=`official_unavailable`\n         (cron 再以上一份 industry_raw 的 chosen 覆蓋,見 `apply_prev_chosen`)。\n    紀錄 = {"finmind": [原始 {industry_category, type, date}, …](API 原順序),\n            "official": {market, code, name, endpoint} | None,\n            "chosen": {"label": str|None, "rule": str}}。⛔ 不臆造:無任何來源 → label None。\n    """\n    from shared.industry_codes import loose_industry_name, official_industry_name\n\n    _unavail = set(unavailable_markets or ())\n    by_id: dict = {}\n    for row in finmind_rows or []:\n        if not isinstance(row, dict):\n            continue\n        sid = str(row.get("stock_id", "")).strip()\n        if not sid:\n            continue\n        by_id.setdefault(sid, []).append({\n            "industry_category": str(row.get("industry_category") or "").strip(),\n            "type": (str(row.get("type")).strip() if row.get("type") is not None else None),\n            "date": (str(row.get("date")).strip() if row.get("date") is not None else None),\n        })\n    out: dict = {}\n    for code in sorted(set(by_id) | set(official or {})):\n        fm = by_id.get(code, [])\n        _ld = [(r["industry_category"], r["date"]) for r in fm if r["industry_category"]]\n        off = (official or {}).get(code)\n        off_rec = None\n        label, rule = None, RULE_NO_OFFICIAL\n        if off is not None:\n            name = official_industry_name(off.get("code"))\n            off_rec = {"market": off.get("market"), "code": off.get("code"), "name": name,\n                       "endpoint": off.get("endpoint")}\n            if name:\n                exact = [x for x in _ld if x[0] == name]\n                loose = [x for x in _ld if loose_industry_name(x[0]) == loose_industry_name(name)]\n                if exact or loose:\n                    label, rule = _finmind_deterministic(exact or loose), RULE_OFFICIAL_MATCH\n                else:\n                    label, rule = name, RULE_OFFICIAL_NAME\n            else:\n                label = _finmind_deterministic(_ld)\n        else:\n            _mk = {_FINMIND_TYPE_MARKET.get(r["type"]) for r in fm} - {None}\n            label = _finmind_deterministic(_ld)\n            if _mk & _unavail:\n                rule = RULE_OFFICIAL_UNAVAILABLE\n        out[code] = {"finmind": fm, "official": off_rec,\n                     "chosen": {"label": label, "rule": rule}}\n    return out\n',
         '        except Exception as e:\n            print(f"[industry/openapi] {url.split(\'/\')[-1]} ❌ "\n                  f"{type(e).__name__}: {e}")\n    return out\n'),
        ('\ndef apply_prev_chosen(raw: dict, prev_raw) -> dict:\n    """`official_unavailable` 的代號 → 沿用上一份 industry_raw 的 chosen.label(有才沿用)。回新 dict。\n\n    沿用時 chosen 追加 `from_prev=True` 與 `prev_rule`;上一份沒有該代號 → 維持 FinMind 決定論、\n    `from_prev=False`。⛔ 不改其他代號。\n    """\n    import copy\n    new = copy.deepcopy(raw or {})\n    _prev = ((prev_raw or {}).get("codes") or {}) if isinstance(prev_raw, dict) else {}\n    for code, rec in (new.get("codes") or {}).items():\n        ch = rec.get("chosen") or {}\n        if ch.get("rule") != RULE_OFFICIAL_UNAVAILABLE:\n            continue\n        p = (_prev.get(code) or {}).get("chosen") or {}\n        if p.get("label"):\n            ch["label"] = p["label"]\n            ch["from_prev"] = True\n            ch["prev_rule"] = p.get("rule")\n        else:\n            ch["from_prev"] = False\n    return new\n\n\ndef industry_map_from_raw(raw) -> dict:\n    """industry_raw → 扁平 {代號: chosen.label}(label 空者不列,⛔ 不臆造)。"""\n    out: dict = {}\n    for code, rec in ((raw or {}).get("codes") or {}).items():\n        lab = ((rec or {}).get("chosen") or {}).get("label")\n        if code and lab:\n            out[str(code)] = str(lab)\n    return out\n\n\ndef get_last_industry_raw() -> dict | None:\n    """最近一次 `fetch_industry_map_bulk()` 的選列紀錄(deep copy);從未呼叫 → None。"""\n    import copy\n    return copy.deepcopy(_LAST_INDUSTRY_RAW) if _LAST_INDUSTRY_RAW else None\n\n\ndef fetch_industry_map_bulk(token: str | None = None) -> dict:\n',
         '\ndef fetch_industry_map_bulk(token: str | None = None) -> dict:\n'),
        ('def fetch_industry_map_bulk(token: str | None = None) -> dict:\n    """全市場 {股票代碼: 產業別} 整表(批 Z43:依官方產業代碼選列)。\n\n',
         'def fetch_industry_map_bulk(token: str | None = None) -> dict:\n    """全市場 {股票代碼: 產業別} 整表。FinMind 主 → openapi 補齊仍缺者。\n\n'),
        ('\n    FinMind TaiwanStockInfo 原始列 + 官方 openapi 產業代碼 → `select_industry_records`。\n    完整紀錄(原始列 / 官方 / chosen / 來源 / 狀態)存 `_LAST_INDUSTRY_RAW`(`get_last_industry_raw()`),\n    由 cron 落地 `data_cache/sector_flow/industry_raw.json`(原始資料不覆寫、可追溯)。\n    §1:兩源皆空 → 回 {}(caller 決定是否致命);絕不臆造產業別。\n',
         '\n    §1:兩源皆空 → 回 {}(caller 決定是否致命);絕不臆造產業別。\n'),
        ('    """\n    import datetime as _dtm\n    _LAST_INDUSTRY_RAW.clear()\n    _tok = token if token is not None else _os.environ.get("FINMIND_TOKEN", "")\n',
         '    """\n    _tok = token if token is not None else _os.environ.get("FINMIND_TOKEN", "")\n'),
        ('    _tok = token if token is not None else _os.environ.get("FINMIND_TOKEN", "")\n    fm_rows = _finmind_industry_rows(_tok)\n    official, status = _official_industry_codes()\n    unavailable = sorted(m for m, s in status.items() if not s.get("ok"))\n    codes = select_industry_records(fm_rows or [], official, unavailable_markets=unavailable)\n    warnings: list[str] = []\n    for m in unavailable:\n        warnings.append(f"官方產業別端點不可用:{m}({status[m].get(\'reason\')})→ 該市場官方查無的代號"\n                        f"記 {RULE_OFFICIAL_UNAVAILABLE}(沿用上一份 chosen,否則 FinMind 決定論)")\n    if fm_rows is None:\n        warnings.append("FinMind TaiwanStockInfo 失敗 → 只有官方代碼可用(官方查無者無產業別)")\n    from shared.industry_codes import OFFICIAL_INDUSTRY_CODE_NAMES, INDUSTRY_SCHEME_VERSION\n    _unknown = sorted({v["code"] for v in official.values()\n                       if v.get("code") not in OFFICIAL_INDUSTRY_CODE_NAMES})\n    if _unknown:\n        warnings.append(f"官方產業別代碼不在代碼表:{_unknown}(⛔ 不猜名稱 → FinMind 決定論)")\n    for w in warnings:\n        print(f"[industry] ⚠️ {w}")\n    _LAST_INDUSTRY_RAW.update({\n        "scheme": INDUSTRY_SCHEME_VERSION,\n        "fetched_at": _dtm.datetime.now(_dtm.timezone.utc).isoformat(),\n        "sources": {"finmind": f"{FINMIND_URL}?dataset=TaiwanStockInfo",\n                    MARKET_TWSE: TWSE_COMPANY_INFO_URL, MARKET_TPEX: TPEX_COMPANY_INFO_URL},\n        "finmind_status": {"ok": fm_rows is not None, "n_rows": len(fm_rows or [])},\n        "official_status": status,\n        "unavailable_markets": unavailable,\n        "warnings": warnings,\n        "codes": codes,\n    })\n    out = industry_map_from_raw(_LAST_INDUSTRY_RAW)\n    _rules: dict = {}\n    for rec in codes.values():\n        _r = rec["chosen"]["rule"]\n        _rules[_r] = _rules.get(_r, 0) + 1\n    print(f"[industry] 選列後 {len(out)} 檔(規則分布 {_rules})")\n    return out\n',
         '    _tok = token if token is not None else _os.environ.get("FINMIND_TOKEN", "")\n    out = _finmind_industry_map(_tok)\n    # 不論 FinMind 成敗都補 openapi:填 FinMind 缺漏(新上市未收錄 / gate)\n    fallback = _openapi_industry_map()\n    for code, ind in fallback.items():\n        out.setdefault(code, ind)\n    print(f"[industry] 合併後 {len(out)} 檔(FinMind + openapi)")\n    return out\n'),
    ),
    _L0: (
        ('#: `fetch_industry_map_bulk` 對不同上市/上櫃 ETF 給的細分標籤不一致\n#: (上市 → "ETF"、上櫃 → "上櫃ETF" 或 "上櫃指數股票型基金(ETF)")。\n#: ~~但泡泡圖三大法人聚合桶只會出現單一 "ETF"~~ —— 批 Z43 更正(事實更正,不是漏刪):\n#: 舊句不實,實際 daily_net 的原始桶同時有 "ETF"、"上櫃ETF"、"上櫃指數股票型基金(ETF)" 三個;\n#: 自批 Z43 起泡泡改在**標準化軸**彙總(`SECTOR_CANONICAL_ALIASES` → 單一 "ETF" 泡泡)。\n#: ⚠️ ETN / 受益證券 / 存託憑證屬不同商品,**不**併入 ETF。\nSECTOR_ETF_CANONICAL: str = "ETF"\n',
         '#: `fetch_industry_map_bulk` 對不同上市/上櫃 ETF 給的細分標籤不一致\n#: (上市 → "ETF"、上櫃 → "上櫃ETF"、部分來源 → "上市/上櫃指數股票型基金(ETF)"),\n#: 但泡泡圖三大法人聚合桶只會出現單一 "ETF"。做持股→泡泡 highlight 交集時,\n#: 需把 ETF 家族細分標籤正規化成同一 canonical,否則持有上櫃 ETF(如 00980D→上櫃ETF)\n#: 永遠對不到 "ETF" 泡泡。⚠️ ETN / 受益證券 / 存託憑證屬不同商品,**不**併入。\nSECTOR_ETF_CANONICAL: str = "ETF"\n'),
        ('\n# ── 批 Z43(客戶 Q-z29＝A):板塊名稱標準化別名表 SSOT ─────────────────────────\n#: 原始板塊標籤 → 標準板塊標籤。**資料層不覆寫**(daily_net.parquet `sector` 欄、ticker_sector.json\n#: 維持原始標籤),只在 L2 `canonicalize_sector_daily`(泡泡彙總前)與持股高亮比對時套用。\n#: 收錄原則:**只**收「官方定義或實際成分確認為同義」者,每項附證據;不因名稱相似就合併。\n#: 證據來源:GitHub runner 探針第 7 輪 run 38191149822(官方 openapi 產業別代碼 × ISIN 公開頁)。\n#: ❌ 刻意不收:「創新版股票/創新板股票」(官方「創新板」是**證券類別**不是產業別,個股各有官方產業別,\n#:    由產業別取法改依官方代碼解決);「農業科技/農業科技業」(新 map 下「農業科技」3 檔成員**皆官方查無**、\n#:    「農業科技業」4 檔為代碼 33 —— 無法證明同代碼,不得合併;舊 map 成員官方為 20/22 亦不同);\n#:    ETN ⛔ 不併入 ETF(官方證券類別不同:ETF CFI CE、ETN CFI CM)。\nSECTOR_CANONICAL_ALIASES: dict[str, str] = {\n    # 證據分兩種(據實):「舊 map」＝批 Z43 前取第一列的 ticker_sector.json 成員 × 官方代碼(探針第 7 輪\n    #   run 38191149822);「新 map」＝改依官方代碼選列後(探針第 8 輪 run 38193131712,\n    #   tests/fixtures/z43_label_official_codes.json,\'-\' ＝ 官方查無)。\n    # 代碼 16「觀光餐旅」:\'觀光事業\' **舊 map** 成員 → openapi 上市 16×17、上櫃 16×24(另 4 檔官方為別的產業)。\n    #   ⚠️ 新 map 下這些股已直接選到 FinMind「觀光餐旅」列,\'觀光事業\' 只剩 1 檔且為官方查無 → 新 map 無法再\n    #   以代碼佐證;保留理由:①舊取法寫入的歷史列(daily_net 回補前)仍帶此標籤;②FinMind 對官方查無標的\n    #   仍可能給此名稱;同義性已由舊 map 的官方代碼證明。\n    "觀光事業": "觀光餐旅",\n    # 代碼 36「數位雲端」:\'數位雲端類\' 舊 map 成員 → 上櫃 36×2;新 map 36×18(與 \'數位雲端\' 36×22 同代碼)\n    "數位雲端類": "數位雲端",\n    # 代碼 35「綠能環保」:\'綠能環保類\' 舊 map → 上櫃 35×2;新 map 35×15(與 \'綠能環保\' 35×31 同代碼)\n    "綠能環保類": "綠能環保",\n    # 代碼 38「居家生活」:\'居家生活類\' 舊 map → 上櫃 38×2;新 map 38×21(與 \'居家生活\' 38×15 同代碼)\n    "居家生活類": "居家生活",\n    # 代碼 31「其他電子業」:\'其他電子類\' 舊 map → 上櫃 31×38;新 map 31×40(與 \'其他電子業\' 31×54 同代碼)\n    "其他電子類": "其他電子業",\n    # 代碼 17「金融保險業」(客戶已裁):\'金融業\' **舊 map** 成員 → 上櫃 17×9;上市 \'金融保險\' → 17×31。\n    #   ⚠️ 新 map 下那 9 檔改選官方名 \'金融保險業\'(見下),\'金融業\' 只剩 6 檔且皆官方查無 → 新 map 無法再以\n    #   代碼佐證;保留理由同 \'觀光事業\'(舊取法歷史列 + FinMind 對官方查無標的的命名),且為客戶明示裁示。\n    "金融業": "金融保險",\n    # ── 以下兩項:改依官方代碼選列後「同一官方代碼卻兩種標籤」(探針第 8 輪 run 38192607977 實測;\n    #    證據＝成員官方代碼完全相同,見 tests/fixtures/z43_label_official_codes.json)──\n    # 代碼 17:\'金融保險業\'(上櫃 9 檔,FinMind 只有「金融業」列、無相符列 → 取官方名)全為 17,\'金融保險\' 為 17×31\n    "金融保險業": "金融保險",\n    # 代碼 37「運動休閒」:\'運動休閒類\' 成員官方代碼 37×8、\'運動休閒\' 37×19\n    "運動休閒類": "運動休閒",\n    # ETF 家族(客戶已裁):官方同屬「ETF」證券類別、CFI 前 2 碼 CE、產業別欄空白(上市 241 / 上櫃 119 檔)。\n    #   成員直接取自**既有**(批 Z43 前即存在、持股高亮已在用)的 `SECTOR_ETF_FAMILY_ALIASES`,不是本批新增;\n    #   其中 \'上市ETF\' / \'指數股票型基金(ETF)\' / \'上市指數股票型基金(ETF)\' 在新舊 map 皆未出現(探針第 7/8 輪),\n    #   保留只為維持既有 ETF 家族行為不變。實際出現者:\'上櫃ETF\'、\'上櫃指數股票型基金(ETF)\'。\n    **{_a: SECTOR_ETF_CANONICAL for _a in sorted(SECTOR_ETF_FAMILY_ALIASES)\n       if _a != SECTOR_ETF_CANONICAL},\n    # ETN:官方同屬「ETN」證券類別、CFI 前 2 碼 CM(上市 15 / 上櫃 6 檔)\n    "指數投資證券(ETN)": "ETN",\n}\n#: 別名表版本(寫進 bubble_latest.json `sector_aliases_version`;別名表任何增刪都要遞增)。\nSECTOR_ALIASES_VERSION: str = "z43-v1"\n\n\n',
         '\n\n'),
        ('def canonical_sector(label) -> str:\n    """原始板塊標籤 → 標準板塊標籤(`SECTOR_CANONICAL_ALIASES` SSOT;不在表內 → 原樣)。\n\n    批 Z43 前只正規化 ETF 家族;起改以別名表為 SSOT(ETF 家族照舊對到 "ETF",持股高亮比對與泡泡\n    標準化軸一致)。純函式、零 I/O。\n    """\n    s = str(label or "").strip()\n',
         'def canonical_sector(label) -> str:\n    """ETF 家族細分標籤 → canonical "ETF";其餘板塊原樣返回(highlight 交集前用)。"""\n    s = str(label or "").strip()\n'),
        ('    s = str(label or "").strip()\n    return SECTOR_CANONICAL_ALIASES.get(s, s)\n\n',
         '    s = str(label or "").strip()\n    return SECTOR_ETF_CANONICAL if s in SECTOR_ETF_FAMILY_ALIASES else s\n\n'),
    ),
}
#: 基底 `7c1adf8a` 原始檔 sha256（`git show 7c1adf8a:<檔> | sha256sum` 實算；寫死以免測試依賴 git）。
Z43_BASE_SHA = {
    _CLOSE: "9ff48f58311add448909c71eb3c12b459096e3dfda32cedd4992ae5ee972da65",
    _L0: "760a90cd7ed961a5004b0fd1eb70d7d3852923bf406aa92b62c1d0d5be4a1e66",
}

_SEQ = [0]


def z43_revert(rel: str, code: str) -> str:
    """現行原始碼 → 本批之前（`7c1adf8a`）原始碼（無 pair 的檔原樣）。舊批次還原鏈串接用。"""
    for new, old in Z43_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def _exec(rel: str, code: str, tag: str):
    _SEQ[0] += 1
    path = _ROOT / rel
    name = f"_z43_{tag}_{_SEQ[0]}"
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(code, str(path), "exec"), m.__dict__)
    return m


def _mut(rel: str, pairs, tag: str = "m"):
    """現行檔逐字置換 `pairs`（每組恰一處）後載入成獨立模組（不影響本尊）。"""
    code = (_ROOT / rel).read_text(encoding="utf-8")
    for new, old in pairs:
        assert code.count(new) == 1, f"{rel} 突變點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return _exec(rel, code, tag)


@functools.lru_cache(maxsize=None)
def z43_pre_module(rel: str):
    """本批之前的模組（只把本批改動換回 `7c1adf8a` 寫法）。"""
    return _exec(rel, z43_revert(rel, (_ROOT / rel).read_text(encoding="utf-8")), "pre")


@pytest.mark.parametrize("rel", sorted(Z43_BASE_SHA))
def test_reverted_source_equals_base_file(rel):
    """還原體逐字 ＝ 基底 `7c1adf8a` 檔 ⇒ 下方「修前」對照跑的是真修前碼。"""
    code = z43_revert(rel, (_ROOT / rel).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z43_BASE_SHA[rel]


def test_older_batch_chains_include_z43():
    """Z39／Z41／Z42 的還原鏈已串接本批（否則它們的 base-sha 自證會轉紅）。"""
    from tests import test_batch_z39 as Z39
    from tests import test_batch_z41 as Z41
    from tests import test_batch_z42 as Z42
    code = Z39.z39_revert(_CLOSE, (_ROOT / _CLOSE).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z39.Z39_BASE_SHA[_CLOSE]
    code = Z41.z41_revert(_CLOSE, (_ROOT / _CLOSE).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z41.Z41_BASE_SHA[_CLOSE]
    code = Z42.z42_revert(_L0, (_ROOT / _L0).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z42.Z42_BASE_SHA[_L0]


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案
# ══════════════════════════════════════════════════════════════════════════
import scripts.update_sector_flow as U  # noqa: E402
import shared.industry_codes as IC  # noqa: E402
import src.data.stock.market_close_fetcher as mcf  # noqa: E402
from shared.sector_flow_thresholds import (  # noqa: E402
    SECTOR_ALIASES_VERSION,
    SECTOR_CANONICAL_ALIASES,
    SECTOR_ETF_FAMILY_ALIASES,
    canonical_sector,
)
from src.compute.sector_flow import (  # noqa: E402
    canonicalize_sector_daily,
    compute_bubble,
)

_FIX = _ROOT / "tests" / "fixtures" / "z43_label_official_codes.json"
_VAL = ["net_amt_yi", "foreign_yi", "trust_yi", "dealer_yi"]


def _fm(sid, cat, typ="twse", date="2026-10-11"):
    return {"stock_id": sid, "industry_category": cat, "type": typ, "date": date,
            "stock_name": "x"}


def _off(code, market="上市"):
    url = mcf.TWSE_COMPANY_INFO_URL if market == "上市" else mcf.TPEX_COMPANY_INFO_URL
    return {"market": market, "code": code, "endpoint": url}


# ── 探針第 7 輪原文重現的 FinMind 多列（列順序即 API 回傳順序）─────────────────────
_FM_ROWS = [
    _fm("2344", "半導體業"), _fm("2344", "電子工業"),
    _fm("2308", "電子工業"), _fm("2308", "電子零組件業"),
    _fm("2330", "半導體業"), _fm("2330", "電子工業"),
    _fm("3105", "半導體業", "tpex"),
    _fm("6177", "建材營造"),                                       # 官方 14 建材營造業(去尾相同)
    _fm("6028", "金融業", "tpex"),                                 # 官方 17 金融保險業(無列相符)
    _fm("2801", "金融保險"),                                       # 官方 17 金融保險業(去尾相同)
    _fm("6870", "數位雲端類", "tpex"), _fm("6870", "數位雲端", "tpex"),  # 官方 36(完全相同優先)
    _fm("0050", "ETF"),
    _fm("00679B", "上櫃指數股票型基金(ETF)", "tpex", "2024-12-30"),
    _fm("00679B", "上櫃ETF", "tpex", "2026-10-11"),
    _fm("9103", "存託憑證"),                                       # 官方代碼 91(名稱空白)
    _fm("7777", "電子工業", "emerging"),                           # 興櫃(官方查無)
]
_OFFICIAL = {
    "2344": _off("24"), "2308": _off("28"), "2330": _off("24"), "3105": _off("24", "上櫃"),
    "6177": _off("14"), "6028": _off("17", "上櫃"), "2801": _off("17"), "6870": _off("36", "上櫃"),
    "9103": _off("91"),
    "1234": _off("24"),                                           # 官方有、FinMind 無(新上市)
}


# ══════════════════════════════════════════════════════════════════════════
# 1. L0 官方代碼表 / 寬鬆比對
# ══════════════════════════════════════════════════════════════════════════
class TestIndustryCodes:
    def test_table_is_probe_original(self):
        t = IC.OFFICIAL_INDUSTRY_CODE_NAMES
        assert len(t) == 37 and "07" not in t                     # 36 項 + '91';官方無 07
        assert t["24"] == "半導體業" and t["17"] == "金融保險業" and t["16"] == "觀光餐旅"
        assert t["13"] == "電子工業" and t["91"] is None
        assert all(len(k) == 2 and k.isdigit() for k in t)

    @pytest.mark.parametrize("a,b", [("建材營造業", "建材營造"), ("其他業", "其他"), ("居家生活類", "居家生活"),
                                     ("其他", "其他"), (" 航運業 ", "航運"), ("金融業", "金融")])
    def test_loose(self, a, b):
        assert IC.loose_industry_name(a) == b

    def test_loose_does_not_equate_finance(self):
        assert IC.loose_industry_name("金融業") != IC.loose_industry_name("金融保險業")


# ══════════════════════════════════════════════════════════════════════════
# 2. L1 選列規則（純函式）
# ══════════════════════════════════════════════════════════════════════════
class TestSelectRecords:
    def _sel(self, rows=_FM_ROWS, official=_OFFICIAL, **kw):
        return mcf.select_industry_records(copy.deepcopy(rows), copy.deepcopy(official), **kw)

    def test_rules(self):
        r = self._sel()
        ch = {k: (v["chosen"]["label"], v["chosen"]["rule"]) for k, v in r.items()}
        M, N, F = mcf.RULE_OFFICIAL_MATCH, mcf.RULE_OFFICIAL_NAME, mcf.RULE_NO_OFFICIAL
        assert ch["2344"] == ("半導體業", M)
        assert ch["2308"] == ("電子零組件業", M)           # 第一列是「電子工業」→ 舊碼取錯
        assert ch["2330"] == ("半導體業", M)
        assert ch["3105"] == ("半導體業", M)
        assert ch["6177"] == ("建材營造", M)               # 保留 FinMind 命名(最少可見變動)
        assert ch["6028"] == ("金融保險業", N)             # FinMind 無相符列 → 官方名
        assert ch["2801"] == ("金融保險", M)
        assert ch["6870"] == ("數位雲端", M)               # 完全相同優先於去尾相同
        assert ch["0050"] == ("ETF", F)
        assert ch["00679B"] == ("上櫃ETF", F)              # 官方查無多列 → date 最新
        assert ch["9103"] == ("存託憑證", F)               # 代碼 91 官方名空白 → FinMind
        assert ch["7777"] == ("電子工業", F)               # 興櫃官方查無 → FinMind(不重分類)
        assert ch["1234"] == ("半導體業", N)               # 新上市只有官方

    def test_no_official_target_is_electronics_or_chem(self):
        """「電子工業」「化學生技醫療」不得因官方有產業別而被選上(官方產業別為該名者 0 檔)。"""
        rows = [_fm("2357", "電子工業"), _fm("2357", "電腦及週邊設備業"),
                _fm("4155", "化學生技醫療"), _fm("4155", "生技醫療業")]
        r = mcf.select_industry_records(rows, {"2357": _off("25"), "4155": _off("22")})
        assert r["2357"]["chosen"]["label"] == "電腦及週邊設備業"
        assert r["4155"]["chosen"]["label"] == "生技醫療業"

    def test_order_independent(self):
        a = self._sel()
        b = self._sel(rows=list(reversed(_FM_ROWS)))
        assert {k: v["chosen"] for k, v in a.items()} == {k: v["chosen"] for k, v in b.items()}

    def test_same_date_lexicographic(self):
        r = mcf.select_industry_records([_fm("X1", "乙"), _fm("X1", "甲")], {})
        assert r["X1"]["chosen"]["label"] == min("乙", "甲")

    def test_raw_rows_preserved(self):
        r = self._sel()
        assert r["2308"]["finmind"] == [
            {"industry_category": "電子工業", "type": "twse", "date": "2026-10-11"},
            {"industry_category": "電子零組件業", "type": "twse", "date": "2026-10-11"}]
        assert r["2308"]["official"] == {"market": "上市", "code": "28", "name": "電子零組件業",
                                         "endpoint": mcf.TWSE_COMPANY_INFO_URL}
        assert r["6028"]["official"]["endpoint"] == mcf.TPEX_COMPANY_INFO_URL

    def test_unknown_code_not_guessed(self):
        r = mcf.select_industry_records([_fm("Y1", "某業")], {"Y1": _off("99")})
        assert r["Y1"]["official"]["name"] is None
        assert r["Y1"]["chosen"] == {"label": "某業", "rule": mcf.RULE_NO_OFFICIAL}
        r = mcf.select_industry_records([], {"Y2": _off("99")})
        assert r["Y2"]["chosen"]["label"] is None                 # 無任何來源 → 不臆造
        assert "Y2" not in mcf.industry_map_from_raw({"codes": r})

    def test_unavailable_market(self):
        r = self._sel(official={k: v for k, v in _OFFICIAL.items() if v["market"] == "上市"},
                      unavailable_markets=["上櫃"])
        assert r["6028"]["chosen"] == {"label": "金融業", "rule": mcf.RULE_OFFICIAL_UNAVAILABLE}
        assert r["00679B"]["chosen"]["rule"] == mcf.RULE_OFFICIAL_UNAVAILABLE
        assert r["0050"]["chosen"]["rule"] == mcf.RULE_NO_OFFICIAL      # 上市 ETF 不受影響
        assert r["2344"]["chosen"]["rule"] == mcf.RULE_OFFICIAL_MATCH
        assert r["7777"]["chosen"]["rule"] == mcf.RULE_NO_OFFICIAL      # 興櫃不屬兩市場

    def test_apply_prev_chosen(self):
        raw = {"codes": self._sel(official={k: v for k, v in _OFFICIAL.items()
                                            if v["market"] == "上市"},
                                  unavailable_markets=["上櫃"])}
        prev = {"codes": {"6028": {"chosen": {"label": "金融保險業", "rule": mcf.RULE_OFFICIAL_NAME}}}}
        new = mcf.apply_prev_chosen(raw, prev)
        assert new["codes"]["6028"]["chosen"] == {"label": "金融保險業",
                                                  "rule": mcf.RULE_OFFICIAL_UNAVAILABLE,
                                                  "from_prev": True,
                                                  "prev_rule": mcf.RULE_OFFICIAL_NAME}
        assert new["codes"]["3105"]["chosen"]["from_prev"] is False   # 上一份沒有 → FinMind
        assert raw["codes"]["6028"]["chosen"]["label"] == "金融業"      # 不改輸入
        assert new["codes"]["2344"]["chosen"] == raw["codes"]["2344"]["chosen"]


# ══════════════════════════════════════════════════════════════════════════
# 3. L1 fetch_industry_map_bulk（mock 網路）
# ══════════════════════════════════════════════════════════════════════════
class _Resp:
    def __init__(self, payload=None, status=200, text=None, url=""):
        self.status_code = status
        self._p = payload
        self.text = text if text is not None else json.dumps(payload, ensure_ascii=False)
        self.content = self.text.encode("utf-8")
        self.url = url
        self.headers = {}

    def json(self):
        if self._p is None:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._p


_TWSE_JSON = [{"出表日期": "1151012", "公司代號": c, "公司名稱": "x", "產業別": v["code"]}
              for c, v in _OFFICIAL.items() if v["market"] == "上市"]
_TPEX_JSON = [{"Date": "1151012", "SecuritiesCompanyCode": c, "CompanyName": "x",
               "SecuritiesIndustryCode": v["code"]}
              for c, v in _OFFICIAL.items() if v["market"] == "上櫃"]
_WRONG_TPEX = "https://openapi.twse.com.tw/v1/opendata/t187ap03_O"


def _net(monkeypatch, mod=mcf, tpex=None, twse=None, fm=None, seen=None, fm_fail=False):
    """mock FinMind(requests.get)與官方(fetch_url)。錯誤的上櫃 URL 一律回 HTML(探針實測)。
    `fm_fail=True` → FinMind 回 HTTP 500(`_finmind_industry_rows` → None)。"""
    _fm_rows = copy.deepcopy(_FM_ROWS if fm is None else fm)

    def _get(url, params=None, headers=None, timeout=None):
        assert "finmind" in url
        if fm_fail:
            return _Resp(None, status=500, text="server error")
        return _Resp({"status": 200, "msg": "success", "data": _fm_rows})

    def _furl(url, params=None, timeout=20, headers=None, attempts=3):
        if seen is not None:
            seen.append(url)
        if url == mcf.TWSE_COMPANY_INFO_URL:
            return twse if twse is not None else _Resp(_TWSE_JSON)
        if url == mcf.TPEX_COMPANY_INFO_URL:
            return tpex if tpex is not None else _Resp(_TPEX_JSON)
        if url == _WRONG_TPEX:
            return _Resp(None, text="<!DOCTYPE html><html>...</html>")
        raise AssertionError(f"未預期 URL {url}")

    monkeypatch.setattr(mod.requests, "get", _get)
    # ⚠️ 只 patch `proxy_helper.fetch_url`(`src.data.proxy` 以 PEP 562 `__getattr__` 即時轉發);
    #    若 patch 套件屬性,undo 會把真函式寫成套件實體屬性 → 遮住轉發 → 污染其他測試的 patch。
    import src.data.proxy.proxy_helper as _ph
    monkeypatch.setattr(_ph, "fetch_url", _furl)
    if hasattr(mod, "_LAST_INDUSTRY_RAW"):
        monkeypatch.setattr(mod, "_LAST_INDUSTRY_RAW", {})


class TestFetchBulk:
    def test_end_to_end(self, monkeypatch):
        seen: list = []
        _net(monkeypatch, seen=seen)
        m = mcf.fetch_industry_map_bulk(token="")
        assert mcf.TPEX_COMPANY_INFO_URL in seen and _WRONG_TPEX not in seen
        assert m["2308"] == "電子零組件業" and m["6028"] == "金融保險業" and m["00679B"] == "上櫃ETF"
        assert "電子工業" not in {m[c] for c in _OFFICIAL if c in m}
        raw = mcf.get_last_industry_raw()
        assert mcf.industry_map_from_raw(raw) == m
        assert raw["unavailable_markets"] == [] and raw["warnings"] == []
        assert raw["official_status"]["上櫃"]["ok"] and raw["official_status"]["上櫃"]["n"] == 3
        assert raw["sources"]["上櫃"] == mcf.TPEX_COMPANY_INFO_URL
        assert raw["scheme"] == IC.INDUSTRY_SCHEME_VERSION

    @pytest.mark.parametrize("bad", [
        _Resp(None, text="<html>not json</html>"),          # 非 JSON(舊錯 URL 的實況)
        _Resp([]),                                            # 0 筆
        _Resp([{"Code": "6028", "Industry": "17"}]),         # 欄名不符 → 不猜欄
        _Resp(None, status=500, text="err"),
    ])
    def test_tpex_unavailable_not_silently_first_row(self, monkeypatch, bad):
        _net(monkeypatch, tpex=bad)
        m = mcf.fetch_industry_map_bulk(token="")
        raw = mcf.get_last_industry_raw()
        assert raw["unavailable_markets"] == ["上櫃"]
        assert any("上櫃" in w for w in raw["warnings"])
        assert raw["codes"]["6028"]["chosen"]["rule"] == mcf.RULE_OFFICIAL_UNAVAILABLE
        assert m["2308"] == "電子零組件業"                    # 上市不受影響
        assert raw["codes"]["00679B"]["chosen"]["label"] == "上櫃ETF"   # 決定論(date 最新),非第一列

    def test_mutant_old_fetch_picks_first_row_and_wrong_url(self, monkeypatch):
        """還原成批 Z43 之前的 L1 → 取第一列(2308→電子工業)、上櫃走錯 URL → 本批斷言轉紅。"""
        Pre = z43_pre_module(_CLOSE)
        seen: list = []
        _net(monkeypatch, mod=Pre, seen=seen)
        m = Pre.fetch_industry_map_bulk(token="")
        assert m["2308"] == "電子工業" and m["00679B"] == "上櫃指數股票型基金(ETF)"
        assert _WRONG_TPEX in seen and mcf.TPEX_COMPANY_INFO_URL not in seen
        with pytest.raises(AssertionError):
            assert m["2308"] == "電子零組件業"

    def test_mutant_tpex_url_reverted_turns_red(self, monkeypatch):
        M = _mut(_CLOSE, [('TPEX_COMPANY_INFO_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"\n',
                           f'TPEX_COMPANY_INFO_URL = "{_WRONG_TPEX}"\n')])
        _net(monkeypatch, mod=M)
        M.fetch_industry_map_bulk(token="")
        assert M.get_last_industry_raw()["unavailable_markets"] == ["上櫃"]   # 錯 URL → 備援失效


# ══════════════════════════════════════════════════════════════════════════
# 4. L0 別名表
# ══════════════════════════════════════════════════════════════════════════
class TestAliases:
    def test_table_content(self):
        A = SECTOR_CANONICAL_ALIASES
        for raw, canon in (("觀光事業", "觀光餐旅"), ("數位雲端類", "數位雲端"), ("綠能環保類", "綠能環保"),
                           ("居家生活類", "居家生活"), ("其他電子類", "其他電子業"), ("金融業", "金融保險"),
                           ("上櫃ETF", "ETF"), ("上櫃指數股票型基金(ETF)", "ETF"), ("指數投資證券(ETN)", "ETN"),
                           ("金融保險業", "金融保險"), ("運動休閒類", "運動休閒")):
            assert A[raw] == canon
        for not_merged in ("創新版股票", "創新板股票", "農業科技", "農業科技業", "ETN", "電子工業", "化學生技醫療"):
            assert not_merged not in A
        assert canonical_sector("ETN") == "ETN" and canonical_sector("指數投資證券(ETN)") != "ETF"
        assert SECTOR_ALIASES_VERSION

    def test_etf_family_preserved(self):
        for a in SECTOR_ETF_FAMILY_ALIASES:
            assert canonical_sector(a) == "ETF"

    def test_idempotent_no_chain(self):
        for raw, canon in SECTOR_CANONICAL_ALIASES.items():
            assert canon not in SECTOR_CANONICAL_ALIASES, f"{canon} 自己又是別名(鏈)"
            assert canonical_sector(canonical_sector(raw)) == canonical_sector(raw)
        assert canonical_sector(" 金融業 ") == "金融保險"
        assert canonical_sector(None) == "" and canonical_sector("半導體業") == "半導體業"

    def test_real_fixture_groups_single_official_code(self):
        """runner 實資料(探針第 8 輪新 map 的 label → 官方代碼計數):每個別名群組的成員官方代碼皆同一;
        且每個官方代碼只對到一個標準標籤(沒有漏收的同代碼異名)。'-' = 官方查無(ETF / 興櫃 / 下市…)。"""
        fx = json.loads(_FIX.read_text(encoding="utf-8"))["labels"]
        assert sum(sum(v.values()) for v in fx.values()) == 3154       # 探針:3154 檔
        groups: dict = {}
        for lab in fx:
            groups.setdefault(canonical_sector(lab), set()).add(lab)
        for canon, mem in groups.items():
            codes = {k for lab in mem for k in fx[lab] if k != "-"}
            assert len(codes) <= 1, f"{canon} ← {sorted(mem)} 官方代碼 {codes}"
        code_canon: dict = {}
        for lab, cc in fx.items():
            for k in cc:
                if k != "-":
                    code_canon.setdefault(k, set()).add(canonical_sector(lab))
        assert {k: v for k, v in code_canon.items() if len(v) > 1} == {}
        for raw in SECTOR_CANONICAL_ALIASES:                       # 別名來源若在實資料出現,證據成立
            if raw in fx and SECTOR_CANONICAL_ALIASES[raw] in fx:
                a = {k for k in fx[raw] if k != "-"}
                b = {k for k in fx[SECTOR_CANONICAL_ALIASES[raw]] if k != "-"}
                assert not a or not b or a == b


# ══════════════════════════════════════════════════════════════════════════
# 5. L2 canonicalize_sector_daily
# ══════════════════════════════════════════════════════════════════════════
def _sd_rows(rows):
    df = pd.DataFrame(rows, columns=["date", "sector", "net_amt_yi", "foreign_yi", "trust_yi",
                                     "dealer_yi", "n_stocks"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def _r(d, s, f, t, de, n=1):
    net = (f + t + de) if not any(isinstance(x, float) and math.isnan(x) for x in (f, t, de)) else np.nan
    return [d, s, net, f, t, de, n]


_NAN = float("nan")


class TestCanonicalize:
    def _base(self):
        return _sd_rows([
            _r("2026-10-07", "金融保險", 10.0, 1.0, -1.0, 40), _r("2026-10-07", "金融業", 2.0, 0.5, 0.0, 8),
            _r("2026-10-07", "ETF", -5.0, 0.0, 1.0, 230), _r("2026-10-07", "上櫃ETF", -1.0, 0.0, 0.0, 26),
            _r("2026-10-07", "上櫃指數股票型基金(ETF)", -2.0, 0.0, 0.5, 90),
            _r("2026-10-07", "半導體業", 50.0, 3.0, -2.0, 200),
            _r("2026-10-08", "金融保險", 11.0, 1.0, -1.0, 41), _r("2026-10-08", "金融業", _NAN, 0.5, 0.0, 8),
            _r("2026-10-08", "ETF", -4.0, 0.0, 1.0, 231), _r("2026-10-08", "上櫃ETF", -1.0, 0.0, 0.0, 26),
            _r("2026-10-08", "半導體業", 40.0, 3.0, -2.0, 201),
        ])

    def test_merge_and_conservation(self):
        sd = self._base()
        before = sd.copy(deep=True)
        c, meta = canonicalize_sector_daily(sd)
        pd.testing.assert_frame_equal(sd, before)                 # 不改輸入(資料層不覆寫)
        assert sorted(c["sector"].unique()) == ["ETF", "半導體業", "金融保險"]
        assert meta["members"]["ETF"] == ["ETF", "上櫃ETF", "上櫃指數股票型基金(ETF)"]
        assert meta["members"]["金融保險"] == ["金融保險", "金融業"]
        assert meta["n_raw_sectors"] == 6 and meta["n_canonical_sectors"] == 3
        d7 = c[c["date"] == pd.Timestamp("2026-10-07")].set_index("sector")
        assert d7.loc["ETF", "foreign_yi"] == pytest.approx(-8.0)
        assert d7.loc["ETF", "n_stocks"] == 346
        assert d7.loc["金融保險", "net_amt_yi"] == pytest.approx((10.0 + 1.0 - 1.0) + (2.0 + 0.5 + 0.0))
        # 每日總額守恆(非 NaN 日)+ n_stocks 守恆
        for col in ["n_stocks", "trust_yi", "dealer_yi"]:
            a = sd.groupby("date")[col].sum(min_count=1)
            b = c.groupby("date")[col].sum(min_count=1)
            assert np.allclose(a.to_numpy(), b.to_numpy())

    def test_nan_member_propagates_not_zero(self):
        c, _ = canonicalize_sector_daily(self._base())
        d8 = c[c["date"] == pd.Timestamp("2026-10-08")].set_index("sector")
        assert math.isnan(d8.loc["金融保險", "foreign_yi"])        # 成員外資 NaN → 合併格 NaN
        assert math.isnan(d8.loc["金融保險", "net_amt_yi"])
        assert d8.loc["金融保險", "trust_yi"] == pytest.approx(1.5)  # 其他分項照算
        assert d8.loc["金融保險", "n_stocks"] == 49
        # 非 NaN 的分項 / 板塊總額照樣守恆
        sd = self._base()
        for col in _VAL:
            ok = c.groupby("date")[col].apply(lambda s: s.notna().all())
            a = sd.groupby("date")[col].sum(min_count=1)[ok]
            b = c.groupby("date")[col].sum(min_count=1)[ok]
            assert np.allclose(a.to_numpy(), b.to_numpy())

    def test_member_absent_counted_not_masked(self):
        """10-08 少一個 ETF 成員標籤 → 以出現者加總(同原始軸「部分個股缺席」語意),只計數。"""
        c, meta = canonicalize_sector_daily(self._base())
        assert meta["n_member_absent_cells"] == 1
        d8 = c[c["date"] == pd.Timestamp("2026-10-08")].set_index("sector")
        assert d8.loc["ETF", "foreign_yi"] == pytest.approx(-5.0)

    def test_singletons_identity_and_flags(self):
        sd = self._base()
        sd["tpex_ok"] = pd.array([True] * 6 + [True, False, True, True, True], dtype="boolean")
        sd["industry_ok"] = pd.array([True] * 10 + [pd.NA], dtype="boolean")
        c, _ = canonicalize_sector_daily(sd)
        s = c[c["sector"] == "半導體業"].reset_index(drop=True)
        r = sd[sd["sector"] == "半導體業"].reset_index(drop=True)
        for col in _VAL + ["n_stocks"]:
            assert s[col].tolist() == r[col].tolist()
        d8 = c[c["date"] == pd.Timestamp("2026-10-08")].set_index("sector")
        assert d8.loc["金融保險", "tpex_ok"] is np.False_ or d8.loc["金融保險", "tpex_ok"] is False
        assert d8.loc["ETF", "tpex_ok"] == True  # noqa: E712
        assert pd.isna(d8.loc["半導體業", "industry_ok"])
        assert str(c["tpex_ok"].dtype) == "boolean"

    def test_duplicate_raises(self):
        sd = pd.concat([self._base(), self._base().iloc[:1]])
        with pytest.raises(ValueError):
            canonicalize_sector_daily(sd)

    def test_empty(self):
        c, meta = canonicalize_sector_daily(pd.DataFrame())
        assert c.empty and meta["n_canonical_sectors"] == 0

    def test_bubble_on_canonical(self):
        """合併後泡泡:X/Y 為成員加總;NaN 傳遞到泡泡 → 未取得(不補 0)。"""
        days = pd.bdate_range("2026-09-01", periods=12)
        rows = []
        for i, d in enumerate(days):
            rows += [_r(d, "ETF", 1.0 + i, 0.0, 0.0, 3), _r(d, "上櫃ETF", 2.0, 0.0, 0.0, 1),
                     _r(d, "金融保險", 1.0, 0.0, 0.0, 2),
                     _r(d, "金融業", _NAN if i == 11 else 1.0, 0.0, 0.0, 1)]
        sd = _sd_rows(rows)
        raw_b, _ = compute_bubble(sd)
        c, _ = canonicalize_sector_daily(sd)
        b, _ = compute_bubble(c)
        R, B = raw_b.set_index("sector"), b.set_index("sector")
        assert B.loc["ETF", "x_yi"] == pytest.approx(R.loc["ETF", "x_yi"] + R.loc["上櫃ETF", "x_yi"])
        assert B.loc["ETF", "y_yi"] == pytest.approx(R.loc["ETF", "y_yi"] + R.loc["上櫃ETF", "y_yi"])
        assert bool(B.loc["金融保險", "unavailable"]) and B.loc["金融保險", "quadrant"] == "未取得"

    def test_mutant_without_nan_mask_turns_red(self):
        M = _mut(_L2, [('        agg[c] = agg[c].mask(agg[f"_na_{c}"] > 0)   # 任一成員 NaN → NaN(不補 0)\n',
                        "        pass\n")])
        c, _ = M.canonicalize_sector_daily(self._base())
        d8 = c[c["date"] == pd.Timestamp("2026-10-08")].set_index("sector")
        assert d8.loc["金融保險", "foreign_yi"] == pytest.approx(11.0)   # NaN 被當 0 → 半套當完整
        with pytest.raises(AssertionError):
            assert math.isnan(d8.loc["金融保險", "foreign_yi"])

    def test_real_daily_net_conservation(self):
        """repo 實資料 daily_net.parquet(cron 產):標準化前後每日三分項 / 合計 / n_stocks 守恆。"""
        p = _ROOT / "data_cache" / "sector_flow" / "daily_net.parquet"
        if not p.exists():
            pytest.skip("無 daily_net.parquet")
        sd = pd.read_parquet(p)
        c, meta = canonicalize_sector_daily(sd)
        assert meta["n_canonical_sectors"] <= meta["n_raw_sectors"]
        for col in _VAL + ["n_stocks"]:
            a = sd.groupby("date")[col].sum(min_count=1)
            b = c.groupby("date")[col].sum(min_count=1)
            assert np.allclose(a.to_numpy(), b.to_numpy(), rtol=0, atol=1e-9, equal_nan=True), col
        assert set(sd["sector"]) >= {s for v in meta["members"].values() for s in v}
        assert int(sd["net_amt_yi"].isna().sum()) == 0 or int(c["net_amt_yi"].isna().sum()) > 0


# ══════════════════════════════════════════════════════════════════════════
# 6. cron(scripts/update_sector_flow)整合
# ══════════════════════════════════════════════════════════════════════════
_TODAY = pd.Timestamp("2026-10-12").date()
_OLD = [d.date() for d in pd.bdate_range(end="2026-10-08", periods=18)]


def _v(f, t, d):
    return {"外資": f, "投信": t, "自營商": d}


def _day():
    return dict(t86={"2308": _v(100.0, 1.0, 0.0), "2801": _v(-5.0, 0.0, 0.0),
                     "0050": _v(10.0, 0.0, 0.0)},
                tpex={"6028": _v(3.0, 0.0, 0.0), "00679B": _v(2.0, 0.0, 1.0),
                      "3105": _v(1.0, 1.0, 1.0)},
                tpex_status="ok",
                twse_close={"2308": 300.0, "2801": 20.0, "0050": 150.0},
                tpex_close={"6028": 15.0, "00679B": 30.0, "3105": 100.0},
                tpex_close_status="ok")


def _run(monkeypatch, tmp_path, today, spec, *, tpex=None, twse=None, fm_fail=False, argv=()):
    import tests.test_batch_z39 as Z39
    Z39._install(monkeypatch, U, spec)
    for k, f in (("CACHE_DIR", ""), ("PARQUET_PATH", "daily_net.parquet"),
                 ("BUBBLE_PATH", "bubble_latest.json"), ("META_PATH", "metadata.json"),
                 ("TICKER_SECTOR_PATH", "ticker_sector.json")):
        monkeypatch.setattr(U, k, tmp_path / f if f else tmp_path)
    _net(monkeypatch, tpex=tpex, twse=twse, fm_fail=fm_fail)   # 真 fetch_industry_map_bulk + mock 網路
    monkeypatch.setattr(U, "_today", lambda: today)
    seen: list = []
    _orig = U._collect_days
    monkeypatch.setattr(U, "_collect_days", lambda days: (seen.append(list(days)), _orig(days))[1])
    rc = U.main(list(argv))
    meta = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    return rc, (seen[0] if seen else []), meta


def _spec(days):
    return {d.strftime("%Y%m%d"): _day() for d in days}


def _old_pq(path, scheme=None):
    rows = []
    for d in _OLD:
        for sec in ("電子工業", "金融業"):
            rows.append({"date": pd.Timestamp(d), "sector": sec, "net_amt_yi": 1.0, "foreign_yi": 1.0,
                         "trust_yi": 0.0, "dealer_yi": 0.0, "n_stocks": 1, "twse_ok": True,
                         "tpex_ok": True, "source": "old", "fetched_at": "old"})
    df = pd.DataFrame(rows)
    if scheme is not None:
        df["industry_scheme"] = scheme
    df.to_parquet(path, index=False)
    return df


class TestCron:
    def test_writes_raw_flat_map_scheme_and_canonical_bubble(self, monkeypatch, tmp_path):
        days = [pd.Timestamp("2026-10-09").date(), _TODAY]
        rc, _seen, meta = _run(monkeypatch, tmp_path, _TODAY, _spec(days), argv=["--bootstrap", "--days", "3"])
        assert rc == 0
        ts = json.loads((tmp_path / "ticker_sector.json").read_text(encoding="utf-8"))
        assert all(isinstance(v, str) for v in ts.values())         # 維持扁平
        assert ts["2308"] == "電子零組件業" and ts["6028"] == "金融保險業" and ts["00679B"] == "上櫃ETF"
        raw = json.loads((tmp_path / "industry_raw.json").read_text(encoding="utf-8"))
        assert raw["codes"]["2308"]["finmind"][0]["industry_category"] == "電子工業"   # 原始列保留
        assert raw["codes"]["2308"]["chosen"] == {"label": "電子零組件業", "rule": mcf.RULE_OFFICIAL_MATCH}
        assert raw["codes"]["6028"]["official"]["market"] == "上櫃"
        assert raw["scheme_written"] == IC.INDUSTRY_SCHEME_VERSION and raw["fetched_at"]
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        assert set(pq["industry_scheme"]) == {IC.INDUSTRY_SCHEME_VERSION}
        # parquet 維持原始標籤(資料層不覆寫)
        assert {"ETF", "上櫃ETF", "金融保險", "金融保險業"} <= set(pq["sector"])
        bj = json.loads((tmp_path / "bubble_latest.json").read_text(encoding="utf-8"))
        assert bj["sector_aliases_version"] == SECTOR_ALIASES_VERSION
        secs = {s["sector"]: s for s in bj["sectors"]}
        assert "上櫃ETF" not in secs and "金融保險業" not in secs
        assert secs["ETF"]["members"] == ["ETF", "上櫃ETF"]                 # 客戶裁示(2):單一 ETF 泡泡
        assert secs["金融保險"]["members"] == ["金融保險", "金融保險業"]      # 同官方代碼 17
        assert secs["半導體業"]["members"] == ["半導體業"]
        bw = meta["bubble_window"]
        assert bw["raw_axis"]["n_sectors"] > bw["canonical_axis"]["n_sectors"] == len(bj["sectors"])
        assert meta["industry"]["scheme"] == IC.INDUSTRY_SCHEME_VERSION
        assert meta["industry"]["rules"][mcf.RULE_OFFICIAL_MATCH] >= 1
        assert meta["sector_aliases_version"] == SECTOR_ALIASES_VERSION

    def test_bubble_totals_conserved_vs_raw_axis(self, monkeypatch, tmp_path):
        days = [pd.Timestamp("2026-10-09").date(), _TODAY]
        _run(monkeypatch, tmp_path, _TODAY, _spec(days), argv=["--bootstrap", "--days", "3"])
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        bj = json.loads((tmp_path / "bubble_latest.json").read_text(encoding="utf-8"))
        raw_b, _ = compute_bubble(pq)
        assert sum(s["x_yi"] for s in bj["sectors"]) == pytest.approx(float(raw_b["x_yi"].sum()))
        assert sorted(m for s in bj["sectors"] for m in s["members"]) == sorted(pq["sector"].unique())

    def test_scheme_stale_backfill_then_stops(self, monkeypatch, tmp_path):
        _old_pq(tmp_path / "daily_net.parquet")                      # 舊列無 industry_scheme
        assert U._tpex_backfill_days(pd.read_parquet(tmp_path / "daily_net.parquet"), _TODAY) == _OLD
        spec = _spec(_OLD + [pd.Timestamp("2026-10-09").date(), _TODAY])
        _rc, seen, meta = _run(monkeypatch, tmp_path, _TODAY, spec)
        assert set(_OLD) <= set(seen)
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        assert set(pq["industry_scheme"]) == {IC.INDUSTRY_SCHEME_VERSION}
        assert "電子工業" not in set(pq["sector"])                   # 舊取法標籤被重算掉
        assert meta["tpex_backfill"]["backfilled_days"]
        nxt = pd.Timestamp("2026-10-13").date()
        _rc, seen2, meta2 = _run(monkeypatch, tmp_path, nxt, {**spec, nxt.strftime("%Y%m%d"): _day()})
        assert not (set(_OLD) & set(seen2))                          # 寫入後即為現行版本 → 不無限回補
        assert meta2["tpex_backfill"]["candidates"] == []

    def test_stale_values(self):
        base = pd.DataFrame({"date": pd.to_datetime(["2026-10-07", "2026-10-07", "2026-10-08"]),
                             "industry_scheme": [IC.INDUSTRY_SCHEME_VERSION, None,
                                                 IC.INDUSTRY_SCHEME_VERSION + IC.INDUSTRY_SCHEME_DEGRADED_SUFFIX]})
        assert U._scheme_stale_dates(base) == {pd.Timestamp("2026-10-07"), pd.Timestamp("2026-10-08")}
        ok = base.assign(industry_scheme=IC.INDUSTRY_SCHEME_VERSION)
        assert U._scheme_stale_dates(ok) == set()
        assert U._scheme_stale_dates(base.drop(columns="industry_scheme")) == \
            {pd.Timestamp("2026-10-07"), pd.Timestamp("2026-10-08")}

    def test_mutant_scheme_not_in_backfill_turns_red(self, monkeypatch, tmp_path):
        M = _mut(_SCRIPT, [("    _ind_bad = _industry_bad_dates(existing) | _scheme_stale_dates(existing)\n",
                            "    _ind_bad = _industry_bad_dates(existing)\n")])
        old = _old_pq(tmp_path / "p.parquet")
        assert M._tpex_backfill_days(old, _TODAY) == []              # 舊取法日子永不重算
        assert U._tpex_backfill_days(old, _TODAY) == _OLD

    def test_official_unavailable_uses_prev_and_degrades(self, monkeypatch, tmp_path):
        days = [pd.Timestamp("2026-10-09").date(), _TODAY]
        _run(monkeypatch, tmp_path, _TODAY, _spec(days), argv=["--bootstrap", "--days", "3"])
        nxt = pd.Timestamp("2026-10-13").date()
        spec = {**_spec(days), nxt.strftime("%Y%m%d"): _day()}
        _rc, _seen, meta = _run(monkeypatch, tmp_path, nxt, spec,
                                tpex=_Resp(None, text="<html>down</html>"))
        raw = json.loads((tmp_path / "industry_raw.json").read_text(encoding="utf-8"))
        assert raw["unavailable_markets"] == ["上櫃"]
        assert raw["codes"]["6028"]["chosen"] == {"label": "金融保險業", "rule": mcf.RULE_OFFICIAL_UNAVAILABLE,
                                                  "from_prev": True, "prev_rule": mcf.RULE_OFFICIAL_NAME}
        ts = json.loads((tmp_path / "ticker_sector.json").read_text(encoding="utf-8"))
        assert ts["6028"] == "金融保險業"                            # 沒退回 FinMind「金融業」
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        _deg = IC.INDUSTRY_SCHEME_VERSION + IC.INDUSTRY_SCHEME_DEGRADED_SUFFIX
        assert set(pq.loc[pq["date"] == pd.Timestamp(nxt), "industry_scheme"]) == {_deg}
        assert any("產業別:" in w and "上櫃" in w for w in meta["warnings"])
        assert pd.Timestamp(nxt).date() in U._tpex_backfill_days(pq, nxt)   # 官方恢復後會重算

    def test_guard_tripped_keeps_previous_raw(self, monkeypatch, tmp_path):
        days = [pd.Timestamp("2026-10-09").date(), _TODAY]
        _run(monkeypatch, tmp_path, _TODAY, _spec(days), argv=["--bootstrap", "--days", "3"])
        before = (tmp_path / "industry_raw.json").read_text(encoding="utf-8")
        big = {f"{9000 + i}": "某產業" for i in range(200)}
        (tmp_path / "ticker_sector.json").write_text(json.dumps(big), encoding="utf-8")
        nxt = pd.Timestamp("2026-10-13").date()
        _rc, _s, meta = _run(monkeypatch, tmp_path, nxt, {**_spec(days), nxt.strftime("%Y%m%d"): _day()})
        assert meta["fetch_diag"].get("industry_map_guard")
        assert (tmp_path / "industry_raw.json").read_text(encoding="utf-8") == before

    def test_service_highlight_uses_canonical(self, monkeypatch):
        """持股(原始標籤 金融保險業 / 上櫃ETF)→ 對到標準化泡泡(金融保險 / ETF);L5 / reader 不需改動。"""
        import src.data.sector_flow.reader as R
        from src.services import sector_flow_service as S
        view = {"ok": True, "sectors": [{"sector": "金融保險"}, {"sector": "ETF"}, {"sector": "半導體業"}],
                "ticker_sector": {"6028": "金融保險業", "00679B": "上櫃ETF", "2330": "半導體業"}}
        monkeypatch.setattr(R, "read_sector_flow_cache", lambda **k: dict(view))
        out = S.get_sector_flow_view(etf_tickers=["00679B.TWO", "6028"], include_stock_watchlists=False)
        assert out["highlight_sectors"] == {"金融保險", "ETF"}


# ══════════════════════════════════════════════════════════════════════════
# 7. QA 修正(兩組獨立 QA 的 non-blocking 項)
# ══════════════════════════════════════════════════════════════════════════
_LOOSE_LINE = ("                loose = [x for x in _ld if loose_industry_name(x[0]) == loose_industry_name(name)]\n")
_LOOSE_SUBSTR = ("                loose = [x for x in _ld if loose_industry_name(name) in loose_industry_name(x[0])"
                 " or loose_industry_name(x[0]) in loose_industry_name(name)]\n")


def _loose_cases(sel):
    """QA1-N1:寬鬆比對必須是「去尾後完全相等」,不是子字串包含。"""
    r = sel([_fm("A31", "其他", "tpex", "2026-10-11"), _fm("A31", "其他電子類", "tpex", "2025-01-01")],
            {"A31": _off("31", "上櫃")})
    assert r["A31"]["chosen"] == {"label": "其他電子類", "rule": mcf.RULE_OFFICIAL_MATCH}
    r = sel([_fm("A20", "其他電子業")], {"A20": _off("20")})
    assert r["A20"]["chosen"] == {"label": "其他業", "rule": mcf.RULE_OFFICIAL_NAME}   # 不得匹配「其他電子業」


class TestQaLooseNotSubstring:
    def test_behaviour(self):
        _loose_cases(mcf.select_industry_records)

    def test_mutant_substring_turns_red(self):
        M = _mut(_CLOSE, [(_LOOSE_LINE, _LOOSE_SUBSTR)])
        with pytest.raises(AssertionError):
            _loose_cases(M.select_industry_records)


def _raw_of(rows):
    """[(代號, label, 官方代碼|None)] → industry_raw 形狀。"""
    return {"codes": {c: {"finmind": [], "official": ({"code": k} if k else None),
                          "chosen": {"label": lab, "rule": "x"}} for c, lab, k in rows}}


class TestQaAliasConsistency:
    def test_pure(self):
        ok = _raw_of([("1", "金融保險", "17"), ("2", "金融保險業", "17"), ("3", "金融業", None),
                      ("4", "運動休閒類", "37"), ("5", "運動休閒", "37"), ("6", "ETF", None)])
        assert U._alias_consistency(ok) == {"code_to_multi_canonical": {}, "canonical_to_multi_code": {}}
        bad = _raw_of([("1", "觀光餐旅", "16"), ("2", "觀光新名", "16"),      # 同代碼兩個標準 → 漏收
                       ("3", "金融保險", "17"), ("4", "金融業", "99")])        # 同標準兩代碼 → 誤併
        r = U._alias_consistency(bad)
        assert r["code_to_multi_canonical"] == {"16": {"觀光餐旅": 1, "觀光新名": 1}}
        assert r["canonical_to_multi_code"] == {"金融保險": {"17": 1, "99": 1}}
        assert U._alias_consistency(None) == {"code_to_multi_canonical": {}, "canonical_to_multi_code": {}}

    def test_cron_writes_structured_warning(self, monkeypatch, tmp_path):
        """別名表漏收(以 identity 模擬)→ 當次 metadata 結構化欄位 + warnings 非空;正常表 → 空。"""
        days = [pd.Timestamp("2026-10-09").date(), _TODAY]
        _rc, _s, meta = _run(monkeypatch, tmp_path, _TODAY, _spec(days), argv=["--bootstrap", "--days", "3"])
        assert meta["industry"]["alias_consistency"] == {"code_to_multi_canonical": {},
                                                         "canonical_to_multi_code": {}}
        assert not any("別名一致性" in w for w in meta["warnings"])
        monkeypatch.setattr(U, "canonical_sector", lambda x: str(x or "").strip())
        _rc, _s, meta = _run(monkeypatch, tmp_path, _TODAY, _spec(days), argv=["--bootstrap", "--days", "3"])
        assert meta["industry"]["alias_consistency"]["code_to_multi_canonical"]["17"] == \
            {"金融保險": 1, "金融保險業": 1}
        assert any("別名一致性" in w and '"17"' in w for w in meta["warnings"])

    def test_mutant_no_warning_turns_red(self, monkeypatch, tmp_path):
        M = _mut(_SCRIPT, [('    if _cons["code_to_multi_canonical"]:\n',
                            '    if False:\n')])
        summ = M._industry_summary(_raw_of([("1", "觀光餐旅", "16"), ("2", "觀光新名", "16")]),
                                   IC.INDUSTRY_SCHEME_VERSION)
        with pytest.raises(AssertionError):
            assert any("別名一致性" in w for w in summ["warnings"])


class TestQaFinmindFailDegrades:
    def test_scheme_degraded_and_backfilled(self, monkeypatch, tmp_path):
        days = [pd.Timestamp("2026-10-09").date(), _TODAY]
        _rc, _s, meta = _run(monkeypatch, tmp_path, _TODAY, _spec(days), fm_fail=True,
                             argv=["--bootstrap", "--days", "3"])
        _deg = IC.INDUSTRY_SCHEME_VERSION + IC.INDUSTRY_SCHEME_DEGRADED_SUFFIX
        assert meta["industry"]["scheme"] == _deg
        assert meta["industry"]["finmind_status"]["ok"] is False
        assert meta["industry"]["unavailable_markets"] == []           # 官方都 ok,只有 FinMind 失敗
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        assert set(pq["industry_scheme"]) == {_deg}
        assert set(U._tpex_backfill_days(pq, _TODAY)) >= set(days)      # FinMind 恢復後會重算

    def test_mutant_not_degraded_turns_red(self, monkeypatch, tmp_path):
        M = _mut(_SCRIPT, [('    if (raw.get("finmind_status") or {}).get("ok") is False:\n',
                            '    if False:\n')])
        monkeypatch.setattr(sys.modules[__name__], "U", M)
        with pytest.raises(AssertionError):
            self.test_scheme_degraded_and_backfilled(monkeypatch, tmp_path)


class TestQaNStocksNotZero:
    def _sd(self):
        sd = _sd_rows([_r("2026-10-07", "金融保險", 1.0, 0.0, 0.0, 40),
                       _r("2026-10-07", "金融業", 1.0, 0.0, 0.0, 8),
                       _r("2026-10-07", "半導體業", 1.0, 0.0, 0.0, 200)])
        sd["n_stocks"] = sd["n_stocks"].astype("float64")
        sd.loc[sd["sector"] == "金融業", "n_stocks"] = np.nan
        return sd

    def _check(self, fn):
        c, _ = fn(self._sd())
        d = c.set_index("sector")
        assert pd.isna(d.loc["金融保險", "n_stocks"])                  # 成員缺 → NA,不是 40
        assert d.loc["半導體業", "n_stocks"] == 200
        assert d.loc["金融保險", "net_amt_yi"] == pytest.approx(2.0)   # 金額不受 n_stocks 缺影響
        assert str(c["n_stocks"].dtype) == "Int64"
        c2, _ = fn(self._sd().drop(columns="n_stocks"))
        assert c2["n_stocks"].isna().all()                              # 無此欄 → 全 NA,不是 0

    def test_behaviour(self):
        self._check(canonicalize_sector_daily)

    def test_mutant_fillna_zero_turns_red(self):
        M = _mut(_L2, [("    agg[\"n_stocks\"] = pd.array([pd.NA if na > 0 else int(round(v))       # 任一成員缺 → NA\n",
                        "    agg[\"n_stocks\"] = pd.array([int(round(v))\n")])
        with pytest.raises(AssertionError):
            self._check(M.canonicalize_sector_daily)


class TestQaEmptyMapKeepsRaw:
    def _go(self, monkeypatch, tmp_path, mod):
        monkeypatch.setattr(sys.modules[__name__], "U", mod)
        (tmp_path / "industry_raw.json").write_text('{"PREV": true}\n', encoding="utf-8")
        (tmp_path / "ticker_sector.json").write_text('{"2330": "半導體業"}\n', encoding="utf-8")
        twse = _Resp([{"公司代號": "2330", "產業別": "99"}])            # 官方 ok,但代碼不在代碼表
        tpex = _Resp([{"SecuritiesCompanyCode": "6028", "SecuritiesIndustryCode": "98"}])
        days = [pd.Timestamp("2026-10-09").date(), _TODAY]
        _run(monkeypatch, tmp_path, _TODAY, _spec(days), fm_fail=True, twse=twse, tpex=tpex,
             argv=["--bootstrap", "--days", "3"])
        raw = mcf.get_last_industry_raw()
        assert raw["codes"] and not mcf.industry_map_from_raw(raw)       # 前提:codes 非空、map 空
        assert (tmp_path / "industry_raw.json").read_text(encoding="utf-8") == '{"PREV": true}\n'
        assert json.loads((tmp_path / "ticker_sector.json").read_text(encoding="utf-8")) == {"2330": "半導體業"}

    def test_behaviour(self, monkeypatch, tmp_path):
        self._go(monkeypatch, tmp_path, U)

    def test_mutant_turns_red(self, monkeypatch, tmp_path):
        M = _mut(_SCRIPT, [("    if not industry_map_from_raw(raw):\n", "    if False:\n")])
        with pytest.raises(AssertionError):
            self._go(monkeypatch, tmp_path, M)


class TestQaMemberAbsentDays:
    def test_meta(self):
        _c, meta = canonicalize_sector_daily(TestCanonicalize()._base())
        assert meta["member_absent_days"] == {"ETF": 1, "半導體業": 0, "金融保險": 0}

    def test_bubble_field(self, monkeypatch, tmp_path):
        d1, d2 = pd.Timestamp("2026-10-09").date(), _TODAY
        spec = _spec([d1, d2])
        day2 = _day()
        day2["tpex"] = {k: v for k, v in day2["tpex"].items() if k != "00679B"}   # 10-12 上櫃 ETF 成員缺席
        spec[d2.strftime("%Y%m%d")] = day2
        _run(monkeypatch, tmp_path, _TODAY, spec, argv=["--bootstrap", "--days", "3"])
        bj = json.loads((tmp_path / "bubble_latest.json").read_text(encoding="utf-8"))
        secs = {s["sector"]: s for s in bj["sectors"]}
        assert secs["ETF"]["n_member_absent_days"] == 1 and secs["ETF"]["members"] == ["ETF", "上櫃ETF"]
        assert all(isinstance(s["n_member_absent_days"], int) for s in bj["sectors"])
        assert secs["半導體業"]["n_member_absent_days"] == 0
