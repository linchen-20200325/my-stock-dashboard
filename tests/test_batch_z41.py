"""批 Z41：上櫃（TPEx）法人與收盤改接官方新網站 JSON（探針驗證欄位語意＋逐列恆等式守衛），
板塊資金自動回補上櫃（客戶 Q-z27 A，受控遷移）。

客戶裁示
--------
- **Q-z27 = A（受控遷移）**：新 parser → regression tests → 舊／新合理性比較 → 正式切換 → 回補窗口。
- 口徑（Q-z24 A'／Q-z25 A，上市上櫃一致）：外資＝外資及陸資(不含外資自營商)；投信；自營商＝自行＋避險；
  外資自營商不加到任何一類；三大法人合計不含外資自營商。不得猜欄位，驗不過 fail loud；Missing ≠ 0。
- 不新增可見文字：已核准的「目前僅含上市資料」在 TPEx 恢復且窗口驗證成功後**自動**消失（Z39 資料驅動）。

Fixture 來源（逐字，探針 run 38104351927／38105028779／38105352894，2026-10-08，派工規格轉述）
- 法人：6488 環球晶／5347 世界／8299 群聯 三列 24 欄原文；fields 24 欄原文；頂層 keys 與 `columnNum=25`。
- 收盤：fields 17 欄原文（含 `<br>` 與空白雜訊）；6488 收盤 1,130.00 高 1,195 低 1,095、5347 收盤 186.50、
  8299 收盤 2,060.00 為探針原值；**其餘收盤欄位（漲跌／開盤／成交股數／成交金額…；5347／8299 的高低）為本測試
  構造值**（僅需滿足「最低≤收盤≤最高」與「成交金額÷成交股數 ∈ [最低,最高]」），不是探針原文。

突變：每條守衛都有「拔掉／改回 → 斷言轉紅」測試（`_mut()` 以原始碼逐字置換、在獨立模組物件中執行，
不影響本尊）。`Z41_REVERT_PAIRS` 為本批 L1 兩檔「修後逐字 → 修前（基底 `f0a32a3b`）逐字」，還原體 sha256 自證；
（整合註：本批原以 Z40 原版 `7de354e8` 為基底開發；整合到 main `f0a32a3b`（Z40＋三個跟進 squash）時，
`_CLOSE` 兩基底同檔、`_INST` 多了 Z40 跟進二的 `_normalize_inst_pivot` NaN 傳遞（與本批 pair 不重疊）⇒
pair 逐字不變，只把 `_INST` 基底 sha 換成 `f0a32a3b` 實檔。）
Z39／Z40 的還原鏈已串接本表（見 `tests/test_batch_z39.py::_z40_pairs`、`tests/test_batch_z40.py::z40_revert_for`）。
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import json
import math
import pathlib
import sys
import time

import pandas as pd
import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_INST = "src/data/core/data_loader_inst_fetchers.py"
_CLOSE = "src/data/stock/market_close_fetcher.py"
_SCHEMA = "shared/tpex_schema.py"
_L2 = "src/compute/sector_flow.py"
_SCRIPT = "scripts/update_sector_flow.py"
_DIAG = "shared/http_diag.py"


# ══════════════════════════════════════════════════════════════════════════
# 0. 還原 / 突變 infra
# ══════════════════════════════════════════════════════════════════════════
#: 本批 L1 兩檔：修後逐字 → 基底 `f0a32a3b` 逐字（difflib 由實檔產生、round-trip 驗過）。
Z41_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _INST: (
        ('    is_foreign_dealer_label)\nfrom shared.tpex_schema import (  # 批 Z41 TPEx 官方新網站 JSON 結構契約 SSOT(L0)\n    TPEX_ALL_GROUPS, TPEX_G_DEALER, TPEX_G_DEALER_HEDGE, TPEX_G_DEALER_SELF,\n    TPEX_G_FOREIGN_DEALER, TPEX_G_FOREIGN_EXCL_FD, TPEX_G_FOREIGN_INCL_FD, TPEX_G_TRUST,\n    TPEX_IDX_OUT_DEALER, TPEX_IDX_OUT_FOREIGN, TPEX_IDX_OUT_TRUST, TPEX_IDX_TOTAL_NET,\n    TPEX_INST_FIELDS, TPEX_INST_MAX_IDENTITY_FAIL_ROW_RATIO, TPEX_INST_MAX_INVALID_ROW_RATIO,\n    TPEX_INST_N_FIELDS, TPEX_INST_REQUIRE_TABLE_DATE, TPEX_INST_TITLE,\n    check_tpex_envelope, parse_tpex_int, tpex_query_date, tpex_redirected_to_error, tpex_roc_date)\nfrom shared.ttls import TTL_15MIN  # noqa: F401  (部分 fetcher inline 引用)\n',
         '    is_foreign_dealer_label)\nfrom shared.roc_calendar import gregorian_to_roc_year\nfrom shared.ttls import TTL_15MIN  # noqa: F401  (部分 fetcher inline 引用)\n'),
        ('\n_TPEX_DAY_CACHE: dict = {}  # {日期字串: {股票代碼: {外資,投信,自營商}}} TPEx 進程級快取（批 Z41：只收 status=ok 的日子）\n# P1 v19.159(團隊稽核 QA-Med):TPEX 暫時性失敗(網路 None/例外)原本把 {} 永久釘進\n',
         '\n_TPEX_DAY_CACHE: dict = {}  # {日期字串: {股票代碼: {外資,投信,自營商}}} TPEx 進程級快取\n# P1 v19.159(團隊稽核 QA-Med):TPEX 暫時性失敗(網路 None/例外)原本把 {} 永久釘進\n'),
        ('# 對稱補上與 T86 相同的短 TTL 負快取(N2c v19.80 當時只補 T86,漏了 TPEX)。\n# ~~「aaData 為空」(TPEX 明確回無資料,如假日)仍永久快取 — 該日資料永不出現,語意正確。~~\n# 批 Z41(客戶 Q-z27＝A 受控遷移)更正 —— 有意識的語意變更,不是漏刪:空表**不再永久快取**,\n#   一律走短 TTL 負快取。舊理由(空表＝假日、資料永不出現)在舊端點成立,但探針實測舊收盤端點\n#   **交易日也回空表**、新端點非交易日亦回 stat=ok 空表 ⇒ 空表無法區分「休市」與「來源故障」,\n#   永久快取會把一次故障釘成整個進程的「沒有資料」(§1)。休市與否改由 caller 以 TWSE 同日判定。\n_TPEX_FAIL_TS: dict = {}   # {日期字串: 失敗時間 epoch};TTL_15MIN 內不重打\n',
         '# 對稱補上與 T86 相同的短 TTL 負快取(N2c v19.80 當時只補 T86,漏了 TPEX)。\n# 「aaData 為空」(TPEX 明確回無資料,如假日)仍永久快取 — 該日資料永不出現,語意正確。\n_TPEX_FAIL_TS: dict = {}   # {日期字串: 失敗時間 epoch};TTL_15MIN 內不重打\n'),
        ('_TPEX_FAIL_TS: dict = {}   # {日期字串: 失敗時間 epoch};TTL_15MIN 內不重打\n# 批 Z39(客戶 Q-z28 診斷):每次**實際打出請求**後記錄該日的結果狀態,\n# 供 cron 區分「TPEx 假日回空」與「交易日 TPEx 失敗」。\n# 批 Z41(客戶 Q-z27＝A):改接官方新網站 `insti/dailyTrade` JSON,狀態值擴充(只有 ok 會回資料、進永久快取):\n#   ok              外殼／欄位／逐列恆等式全部通過\n#   empty           stat=ok、日期回聲正確,但 totalCount=0 且 data=[](休市或交易日故障,由 caller 對照 TWSE)\n#   http_none       fetch_url 回 None 或非 200(網路/proxy/非 2xx)\n#   redirect_error  被轉往官方 /errors 錯誤頁(舊端點下架的實際症狀:302 → HTML 404 頁、最終 200)\n#   json_error      回應不是 JSON(改版或擋爬回 HTML)\n#   schema_error    stat≠ok／日期回聲不符(含回退前一交易日)／title 不符／fields 非逐字 24 欄／列長≠24\n#   identity_failed 任一列逐列恆等式不成立(7 組 買−賣＝超、G1＋G2＝G3、G5＋G6＝G7、T＝G1＋G4＋G7)\n#   parse_error     不可解析列比例 > TPEX_INST_MAX_INVALID_ROW_RATIO\n#   exception       其他例外\n#   (Z39 的 `col_unverified`「欄位驗證失敗仍用預設索引回資料」語意已廢除 —— 新 parser 驗不過一律不回資料,\n#    歸入 schema_error / identity_failed;舊狀態字串不再產生。)\n# 快取命中 / 負快取命中不重設狀態(沿用上一次實際請求的結果)。\n',
         '_TPEX_FAIL_TS: dict = {}   # {日期字串: 失敗時間 epoch};TTL_15MIN 內不重打\n# 批 Z39(客戶 Q-z28 診斷;零行為變更):每次**實際打出請求**後記錄該日的結果狀態,\n# 供 cron 區分「TPEx 假日回空」與「交易日 TPEx 失敗」。回傳值與快取語意一字不變。\n#   ok             JSON 有 aaData 且欄位驗證(buy-sell≈net)通過\n#   empty          JSON 正常但 aaData 空(假日或 TPEx 交易日回空,需由 caller 對照 TWSE 判定)\n#   http_none      fetch_url 回 None(網路/proxy/非 2xx)\n#   json_error     回應不是 JSON(例:改版或擋爬回 HTML)\n#   col_unverified 欄位驗證 for/else 失敗(仍沿用預設索引回資料,但不得當成成功)\n#   exception      其他例外\n# 快取命中 / 負快取命中不重設狀態(沿用上一次實際請求的結果)。\n'),
        ('TPEX_DAY_STATUS_OK: str = "ok"\n#: 批 Z41:`get_tpex_day_status` 可能回傳的全部狀態(只有 ok 代表有可用資料)。\nTPEX_DAY_STATUSES: tuple[str, ...] = (\n    "ok", "empty", "http_none", "redirect_error", "json_error", "schema_error",\n    "identity_failed", "parse_error", "exception")\n#: 批 Z41:櫃買中心官方新網站「三大法人買賣明細資訊」JSON(探針 run 38104351927 等驗證)。\nTPEX_INST_URL: str = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"\n\n',
         'TPEX_DAY_STATUS_OK: str = "ok"\n\n'),
        ('\ndef _tpex_day_fail(ds: str, status: str, r, reason: str) -> dict:\n    """批 Z41:非 ok 統一出口 —— 記狀態 + 短 TTL 負快取(**不**進永久快取)+ log(含洗過的 body)。"""\n    import time as _t_tpf\n    _TPEX_DAY_DIAG[ds] = status\n    _TPEX_FAIL_TS[ds] = _t_tpf.time()\n    print(f\'[TPEx] {ds} 非 ok（{status}）：{reason}\')\n    if r is not None:\n        _log_tpex_body(ds, status, r)\n    return {}\n\n\ndef _tpex_lots(shares: int | None) -> float:\n    """股 → 張。批 Z41 修正(QA L1):與上市 `_get_t86_day` 內 `_lots` **同一規則**\n    `round(v / 1000, 1)`(None → NaN);兩者一致性由 tests/test_batch_z41 逐值比對守住。"""\n    return float(\'nan\') if shares is None else round(shares / 1000, 1)\n\n\n_TPEX_NAN_ROW: dict = {\'外資\': float(\'nan\'), \'投信\': float(\'nan\'), \'自營商\': float(\'nan\')}\n\n\ndef _parse_tpex_inst_rows(ds: str, data: list) -> tuple[str, str, dict]:\n    """批 Z41:`tables[0].data` 逐列驗證 → (status, reason, day_data)。純解析,無 I/O。\n\n    - 列長 ≠ 24 → schema_error(整日)。\n    - 批 Z41 修正(QA M1):代號重複 / 任一數值欄不可解析 → 該代號**輸出三分項 NaN**(缺值,⛔ 不當 0,\n      也不整檔省略 —— 省略會讓 L2 當成「沒有這檔」而 0 貢獻、metadata 看不到),口徑同上市 T86\n      (缺欄／髒值 → NaN)。代號空 → 無法輸出,只計數。無效列比例 > TPEX_INST_MAX_INVALID_ROW_RATIO\n      → parse_error(整日)。\n    - 批 Z41 修正(QA M2)恆等式分級(容差 0):\n      * **語意守衛** G1＋G2＝G3(買/賣/超任一)不成立 → 整日 identity_failed(G1/G3 對調的唯一偵測,\n        不得部分採用);\n      * **資料守衛** 7 組 買−賣＝超、G5＋G6＝G7、T＝G1超＋G4超＋G7超 不成立 → 該代號三分項 NaN 並計數;\n        此類列比例 > TPEX_INST_MAX_IDENTITY_FAIL_ROW_RATIO → 整日 identity_failed。\n    - G2(外資自營商)任一列非零 → warning(G1/G3 區分首次有數值證據,且已由 G1＋G2＝G3 逐列驗過)。\n    - 輸出口徑(Q-z24 A\'/Q-z25 A,同上市 T86):外資＝G1 超、投信＝G4 超、自營商＝G7 超;\n      股 → 張 `_tpex_lots`(同 T86 `round(v/1000, 1)`)。\n    """\n    n_cols = TPEX_INST_N_FIELDS\n    bad_len = [i for i, row in enumerate(data)\n               if not isinstance(row, (list, tuple)) or len(row) != n_cols]\n    if bad_len:\n        return (\'schema_error\',\n                f\'{len(bad_len)} 列長度≠{n_cols}(首例第 {bad_len[0]} 列)\', {})\n    rows: list = []\n    codes_seen: dict = {}\n    for row in data:\n        code = str(row[0]).strip()\n        vals = [None, None] + [parse_tpex_int(row[i]) for i in range(2, n_cols)]\n        rows.append((code, vals, all(v is not None for v in vals[2:])))\n        if code:\n            codes_seen[code] = codes_seen.get(code, 0) + 1\n    parsed: dict = {}\n    nan_codes: set = set()\n    invalid: list = []\n    for code, vals, ok in rows:\n        if not code:\n            invalid.append(\'<空代號>\')                # 無代號 → 無法輸出,只計數\n        elif not ok or codes_seen[code] > 1:          # 不可解析 / 代號重複(兩列皆不可信)\n            invalid.append(code)\n            nan_codes.add(code)\n        else:\n            parsed[code] = vals\n    if invalid:\n        print(f\'[TPEx] ⚠️ {ds} 不可解析/重複代號列 {len(invalid)}/{len(data)}\'\n              f\'(該代號三分項 NaN,不當 0):{invalid[:10]}\')\n        if len(invalid) / len(data) > TPEX_INST_MAX_INVALID_ROW_RATIO:\n            return (\'parse_error\', f\'不可解析列 {len(invalid)}/{len(data)} > \'\n                    f\'{TPEX_INST_MAX_INVALID_ROW_RATIO:.0%}\', {})\n    sem_fails: list = []\n    data_fail_codes: list = []\n    n_g2_nonzero = 0\n    g1, g2, g3 = TPEX_G_FOREIGN_EXCL_FD, TPEX_G_FOREIGN_DEALER, TPEX_G_FOREIGN_INCL_FD\n    g4, g5, g6, g7 = TPEX_G_TRUST, TPEX_G_DEALER_SELF, TPEX_G_DEALER_HEDGE, TPEX_G_DEALER\n    for code, v in parsed.items():\n        for k in range(3):\n            if v[g1[k]] + v[g2[k]] != v[g3[k]]:\n                sem_fails.append(f\'{code}:G1+G2≠G3[{k}]\')\n        bad = [gi for gi, (b, s, n) in enumerate(TPEX_ALL_GROUPS, start=1) if v[b] - v[s] != v[n]]\n        bad += [f\'G5+G6≠G7[{k}]\' for k in range(3) if v[g5[k]] + v[g6[k]] != v[g7[k]]]\n        if v[TPEX_IDX_TOTAL_NET] != v[g1[2]] + v[g4[2]] + v[g7[2]]:\n            bad.append(\'T\')\n        if bad:\n            data_fail_codes.append(f\'{code}:{bad}\')\n            nan_codes.add(code)\n        if v[g2[0]] or v[g2[1]] or v[g2[2]]:\n            n_g2_nonzero += 1\n    if sem_fails:\n        return (\'identity_failed\', f\'語意守衛 G1+G2=G3 不成立 {len(sem_fails)} 處\'\n                f\'(疑似 G1/G3 欄位對調,整日不採用;首例 {sem_fails[:5]})\', {})\n    if data_fail_codes:\n        print(f\'[TPEx] ⚠️ {ds} 資料守衛(買−賣=超/G5+G6=G7/T)不成立 {len(data_fail_codes)}/{len(data)} 列\'\n              f\'(該代號三分項 NaN):{data_fail_codes[:5]}\')\n        if len(data_fail_codes) / len(data) > TPEX_INST_MAX_IDENTITY_FAIL_ROW_RATIO:\n            return (\'identity_failed\', f\'資料守衛不成立列 {len(data_fail_codes)}/{len(data)} > \'\n                    f\'{TPEX_INST_MAX_IDENTITY_FAIL_ROW_RATIO:.0%}(首例 {data_fail_codes[:5]})\', {})\n    if n_g2_nonzero:\n        print(f\'[TPEx] ⚠️ {ds} 外資自營商(G2)非零 {n_g2_nonzero} 列 —— G1(不含)/G3(含)首次有數值\'\n              \'證據可區分,已逐列驗 G1+G2=G3 通過\')\n    day_data = {code: {\'外資\': _tpex_lots(v[TPEX_IDX_OUT_FOREIGN]),\n                       \'投信\': _tpex_lots(v[TPEX_IDX_OUT_TRUST]),\n                       \'自營商\': _tpex_lots(v[TPEX_IDX_OUT_DEALER])}\n                for code, v in parsed.items() if code not in nan_codes}\n    for c in nan_codes:\n        day_data[c] = dict(_TPEX_NAN_ROW)\n    return TPEX_DAY_STATUS_OK, \'\', day_data\n\n\ndef _get_tpex_day(ds: str) -> dict:\n',
         '\ndef _get_tpex_day(ds: str) -> dict:\n'),
        ('    """抓取 TPEx 特定日期的全市場法人資料（上櫃股），進程內快取。\n    回傳 {股票代碼: {\'外資\':float, \'投信\':float, \'自營商\':float}}，單位：張\n\n    批 Z41(客戶 Q-z27＝A 受控遷移):改接櫃買中心官方新網站 `insti/dailyTrade`(sect=EW、西元\n    `YYYY/MM/DD`)。口徑同上市 `_get_t86_day`(Z40):外資＝外資及陸資(不含外資自營商)、投信、\n    自營商＝自行＋避險;外資自營商不加到任何一類。守衛(任一不過 → 非 ok、回 {}、短 TTL 負快取):\n    轉址 /errors、非 JSON、stat、日期回聲(頂層 YYYYMMDD + tables[0] 民國)、title、fields 逐字 24 欄、\n    列長、數值可解析(無效列 ≤1%)、逐列恆等式。只有 ok 進 `_TPEX_DAY_CACHE`(永久)。\n    """\n    if ds in _TPEX_DAY_CACHE:\n',
         '    """抓取 TPEx 特定日期的全市場法人資料（上櫃股），進程內快取。\n    回傳 {股票代碼: {\'外資\':float, \'投信\':float, \'自營商\':float}}，單位：張"""\n    if ds in _TPEX_DAY_CACHE:\n'),
        ("        return {}   # 負快取生效中(短 TTL),不重打\n    HDR = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json, */*',\n           'Referer': 'https://www.tpex.org.tw/'}\n",
         "        return {}   # 負快取生效中(短 TTL),不重打\n    HDR = {'User-Agent': 'Mozilla/5.0', 'Accept': '*/*',\n           'Referer': 'https://www.tpex.org.tw/'}\n"),
        ('    try:\n        r = _fetch_url_dl(\n',
         "    try:\n        dt = datetime.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))\n        roc_year = gregorian_to_roc_year(dt.year)\n        roc_date = f'{roc_year}/{dt.month:02d}/{dt.day:02d}'\n        r = _fetch_url_dl(\n"),
        ("        r = _fetch_url_dl(\n            TPEX_INST_URL,\n            params={'type': 'Daily', 'sect': 'EW', 'date': tpex_query_date(ds),\n                    'id': '', 'response': 'json'},\n            headers=HDR, timeout=5)\n",
         "        r = _fetch_url_dl(\n            'https://www.tpex.org.tw/web/stock/3insti/daily_report/3itrade_hedge_result.php',\n            params={'l': 'zh-tw', 'se': 'EW', 't': 'D', 'd': roc_date, 'o': 'json'},\n            headers=HDR, timeout=5)\n"),
        ('        if r is None:\n            return _tpex_day_fail(ds, \'http_none\', None, \'fetch_url 回 None\')\n        if getattr(r, \'status_code\', 200) != 200:\n            return _tpex_day_fail(ds, \'http_none\', r, f\'HTTP {getattr(r, "status_code", None)}\')\n        if tpex_redirected_to_error(r):\n            return _tpex_day_fail(ds, \'redirect_error\', r,\n                                  f\'被轉往官方錯誤頁 url={getattr(r, "url", None)!r}\')\n        try:\n',
         "        if r is None:\n            _TPEX_DAY_DIAG[ds] = 'http_none'\n            _TPEX_FAIL_TS[ds] = _t_tp.time()   # P1:暫時性 → 短 TTL 負快取,不永久釘\n            return {}\n        try:\n"),
        ("        except ValueError as e:\n            # 批 Z39:非 JSON(改版/擋爬 HTML)單獨記狀態 + 印 body\n            return _tpex_day_fail(ds, 'json_error', r, f'{type(e).__name__}: {e}')\n        _st, _why, t0 = check_tpex_envelope(j, ds, title_exact=TPEX_INST_TITLE,\n                                            require_table_date=TPEX_INST_REQUIRE_TABLE_DATE)\n        if _st != TPEX_DAY_STATUS_OK:\n            return _tpex_day_fail(ds, _st, r, _why)\n        fields = tuple(str(f).strip() for f in (t0.get('fields') or []))\n        if fields != TPEX_INST_FIELDS:\n            return _tpex_day_fail(ds, 'schema_error', r,\n                                  f'fields 非逐字 {TPEX_INST_N_FIELDS} 欄常數'\n                                  f'(實得 {len(fields)} 欄:{list(fields)})')\n        _st, _why, day_data = _parse_tpex_inst_rows(ds, t0['data'])\n        if _st != TPEX_DAY_STATUS_OK:\n            return _tpex_day_fail(ds, _st, r, _why)\n        _TPEX_DAY_CACHE[ds] = day_data\n",
         "        except ValueError as e:\n            # 批 Z39:非 JSON(改版/擋爬 HTML)單獨記狀態 + 印 body;回傳與負快取同原 except 分支\n            _TPEX_DAY_DIAG[ds] = 'json_error'\n            _log_tpex_body(ds, 'json_error', r)\n            print(f'[TPEx] {ds} 失敗: {e}')\n            _TPEX_FAIL_TS[ds] = _t_tp.time()\n            return {}\n        rows_data = j.get('aaData', [])\n        if not rows_data:\n            _TPEX_DAY_DIAG[ds] = 'empty'\n            _log_tpex_body(ds, 'empty', r)\n            _TPEX_DAY_CACHE[ds] = {}\n            return {}\n\n        def _pn_tp(row, idx):\n            if idx is None or idx >= len(row): return 0.0\n            try: return round(int(str(row[idx]).replace(',', '').replace('+', '') or 0) / 1000, 1)\n            # v19.82:裸 except 收窄(§3.3);髒儲存格 → 0.0 為既有 fail-token 語意\n            except (ValueError, TypeError): return 0.0\n\n        def _int_tp(row, idx):\n            try: return int(str(row[idx]).replace(',', '').replace('+', '') or 0)\n            # v19.82:裸 except 收窄(§3.3);此 helper 無 idx 前置守衛,補 IndexError\n            except (ValueError, TypeError, IndexError): return 0\n\n        # ── 動態偵測欄位索引（sColumns 或 buy-sell-net 驗證）──────────\n        # TPEx 標準格式：[0]代號 [1]名稱\n        # 外資 [2]買 [3]賣 [4]淨  投信 [5]買 [6]賣 [7]淨\n        # 自營(自行) [8]買 [9]賣 [10]淨  [11..13]避險  [14]合計\n        f_idx, t_idx, d_idx = 4, 7, 10  # 預設索引\n        _status = TPEX_DAY_STATUS_OK   # 批 Z39:for/else 失敗 → col_unverified\n\n        # 用第一筆有效資料驗證 buy - sell ≈ net（容許 1 張以內誤差）\n        for _sample in rows_data[:5]:\n            if len(_sample) < 11: continue\n            _f_buy = _int_tp(_sample, 2); _f_sell = _int_tp(_sample, 3); _f_net = _int_tp(_sample, 4)\n            _t_buy = _int_tp(_sample, 5); _t_sell = _int_tp(_sample, 6); _t_net = _int_tp(_sample, 7)\n            if abs(_f_net - (_f_buy - _f_sell)) <= 1000 and abs(_t_net - (_t_buy - _t_sell)) <= 1000:\n                break  # 驗證通過，使用預設索引\n        else:\n            # 若驗證全失敗，嘗試欄位較少的格式（部分 TPEx API 版本省略避險欄）\n            # [0]代號 [1]名稱 [2]外買 [3]外賣 [4]外淨 [5]投買 [6]投賣 [7]投淨 [8]自買 [9]自賣 [10]自淨\n            print(f'[TPEx] {ds} 欄位驗證失敗，row長度={len(rows_data[0]) if rows_data else 0}，使用預設索引')\n            _status = 'col_unverified'\n            _log_tpex_body(ds, _status, r)\n\n        day_data = {}\n        for row in rows_data:\n            code = str(row[0]).strip()\n            if not code or len(row) < 11: continue\n            day_data[code] = {\n                '外資': _pn_tp(row, f_idx),\n                '投信': _pn_tp(row, t_idx),\n                '自營商': _pn_tp(row, d_idx),\n            }\n        _TPEX_DAY_CACHE[ds] = day_data\n"),
        ("        _TPEX_DAY_CACHE[ds] = day_data\n        _TPEX_DAY_DIAG[ds] = TPEX_DAY_STATUS_OK\n        print(f'[TPEx] {ds} ({tpex_roc_date(ds)}): {len(day_data)} 支(官方新網站 dailyTrade,守衛全過)')\n        return day_data\n",
         "        _TPEX_DAY_CACHE[ds] = day_data\n        _TPEX_DAY_DIAG[ds] = _status\n        print(f'[TPEx] {ds} ({roc_date}): {len(day_data)} 支 idx=({f_idx},{t_idx},{d_idx})')\n        return day_data\n"),
        ("    except Exception as e:\n        return _tpex_day_fail(ds, 'exception', r, f'{type(e).__name__}: {e}')\n\n",
         "    except Exception as e:\n        print(f'[TPEx] {ds} 失敗: {e}')\n        _TPEX_DAY_DIAG[ds] = 'exception'\n        if r is not None:\n            _log_tpex_body(ds, 'exception', r)\n        _TPEX_FAIL_TS[ds] = _t_tp.time()   # P1:暫時性 → 短 TTL 負快取,不永久釘\n        return {}\n\n"),
        ('    failed：同 `_fetch_twse_inst_fallback`（鍵 `\'tpex\'`；回答 ＝ 日資料進了 `_TPEX_DAY_CACHE`）。\n\n    批 Z41（客戶 Q-z27＝A）語意更正：`_get_tpex_day` 只有 status=ok 的日子進 `_TPEX_DAY_CACHE`，\n    空表（empty）／轉址／schema／恆等式失敗一律短 TTL 負快取 ⇒ 「回答」＝ 該日通過全部守衛。\n    ~~空表（假日）算回答~~（舊端點把空表永久快取，因此被算成「有回答」）—— 有意識的語意變更，\n    不是漏刪：交易日空表無法與故障區分，算「有回答」會把 TPEx 全面故障誤報成「這檔沒有上櫃法人資料」；\n    10 個平日內必有交易日，真休市日夾在其中不會讓整段被判失敗。\n\n    批 Z41 修正二（QA N1）：`_get_tpex_day` 對無效代號回三分項全 NaN（M1）。該日該股三分項**全 NaN**\n    → 視為此股該日無資料、**不加入 rows**（否則會長出全 NaN 的法人欄 → `_inst_src=\'tpex\'` →\n    下游 D2 `fillna(0)` 把「未取得」顯示成 0）；所有日都如此 → 不產生法人欄，走既有缺值路徑\n    （`_inst_src=\'missing\'`）。部分分項 NaN 的日子照常加入、維持 NaN（下游 D2 是否補 0 屬既有取捨，不在此改）。\n    """\n',
         '    failed：同 `_fetch_twse_inst_fallback`（鍵 `\'tpex\'`；回答 ＝ 日資料進了 `_TPEX_DAY_CACHE`）。\n    """\n'),
        ('        rows = []\n        _n_all_nan = 0\n        base = datetime.date.today()\n',
         '        rows = []\n        base = datetime.date.today()\n'),
        ("            if stock_id in day:\n                _v = day[stock_id]\n                if all(pd.isna(_v.get(_k)) for _k in ('外資', '投信', '自營商')):\n                    _n_all_nan += 1      # 批 Z41 修正二(QA N1):全 NaN = 該日此股無資料,不入 rows\n                    continue\n                rows.append({'date': d, **_v})\n        if _n_all_nan:\n            print(f'[TPEx] ⚠️ {stock_id} {_n_all_nan} 日官方列無效(三分項全 NaN)→ 視為該日未取得,不補 0')\n        if rows:\n",
         "            if stock_id in day:\n                rows.append({'date': d, **day[stock_id]})\n        if rows:\n"),
    ),
    _CLOSE: (
        ('   - `fetch_twse_close_day(ds)` : TWSE MI_INDEX(帶 date,官方 T1、免 token),回 {code: close}\n   - `fetch_tpex_close_day(ds)` : TPEX 上櫃每日收盤(官方 T1、免 token;批 Z41 改接官方新網站\n     `afterTrading/otc` JSON,帶西元 date,欄位以清洗後完全相等定位 + 逐列/整表守衛)\n   兩者皆「逐日全市場」介面(給定 YYYYMMDD 回當日全市場),bootstrap 逐日回補 +\n',
         '   - `fetch_twse_close_day(ds)` : TWSE MI_INDEX(帶 date,官方 T1、免 token),回 {code: close}\n   - `fetch_tpex_close_day(ds)` : TPEX 上櫃每日收盤(帶 ROC date,官方 T1、免 token)\n   兩者皆「逐日全市場」介面(給定 YYYYMMDD 回當日全市場),bootstrap 逐日回補 +\n'),
        ('\nimport os as _os\n',
         '\nimport datetime as _dt\nimport os as _os\n'),
        ('from shared.http_diag import scrubbed_body_head\nfrom shared.tpex_schema import (  # 批 Z41 TPEx 官方新網站 JSON 結構契約 SSOT(L0)\n    TPEX_CLOSE_COL_AMOUNT, TPEX_CLOSE_COL_CLOSE, TPEX_CLOSE_COL_CODE, TPEX_CLOSE_COL_HIGH,\n    TPEX_CLOSE_COL_LOW, TPEX_CLOSE_COL_VOLUME, TPEX_CLOSE_N_FIELDS, TPEX_CLOSE_REQUIRE_TABLE_DATE,\n    TPEX_CLOSE_REQUIRED_COLS,\n    TPEX_CLOSE_TITLE_PREFIX, TPEX_CLOSE_UNIT_GUARD_MIN_PASS_RATIO, TPEX_CLOSE_VWAP_REL_TOL,\n    check_tpex_envelope, clean_tpex_field_name, parse_tpex_price, tpex_query_date,\n    tpex_redirected_to_error, tpex_roc_date)\n\n',
         'from shared.http_diag import scrubbed_body_head\nfrom shared.roc_calendar import gregorian_to_roc_year\n\n'),
        ('\n#: 批 Z39(客戶 Q-z28 診斷):`fetch_tpex_close_day(ds)` 最近一次呼叫的結果狀態。\n#:   ok / empty(空表)/ parse_zero(有列但解析 0 筆)/ http_none(None)/\n#:   http_error(非 200)/ json_error(非 JSON)/ exception。\n#: 批 Z41(客戶 Q-z27＝A):改接官方新網站 `afterTrading/otc`,新增\n#:   redirect_error(轉往 /errors)/ schema_error(stat／日期回聲／title／fields 非 17 欄或必要欄名找不到／列長)/\n#:   unit_error(整表單位守衛:有成交列「成交金額÷成交股數 ∈ [最低,最高]」成立率不足)。只有 ok 回資料。\n_TPEX_CLOSE_DIAG: dict[str, str] = {}\n',
         '\n#: 批 Z39(客戶 Q-z28 診斷;零行為變更):`fetch_tpex_close_day(ds)` 最近一次呼叫的結果狀態。\n#:   ok / empty(aaData 空)/ parse_zero(有列但解析 0 筆)/ http_none(None)/\n#:   http_error(非 200)/ json_error(非 JSON)/ exception。回傳值一字不變。\n_TPEX_CLOSE_DIAG: dict[str, str] = {}\n'),
        ('_TPEX_CLOSE_DIAG: dict[str, str] = {}\n#: 批 Z41:櫃買中心官方新網站「上櫃股票每日收盤行情(不含定價)」JSON(探針 run 38105352894 等驗證)。\nTPEX_CLOSE_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc"\n\n',
         '_TPEX_CLOSE_DIAG: dict[str, str] = {}\n\n'),
        ('\ndef _tpex_close_fail(ds: str, status: str, r, reason: str) -> dict:\n    """批 Z41:非 ok 統一出口 —— 記狀態 + log(含洗過的 body 前 500 字)。"""\n    _TPEX_CLOSE_DIAG[ds] = status\n    _body = f" body[:500]={scrubbed_body_head(r)!r}" if r is not None else ""\n    print(f"[TPEX close] {ds} 非 ok({status}):{reason}{_body}")\n    return {}\n\n\ndef _parse_tpex_close_rows(ds: str, fields: list, data: list) -> tuple[str, str, dict]:\n    """批 Z41:收盤表欄位定位 + 逐列守衛 + 整表單位守衛 → (status, reason, {代號: 收盤})。純解析。\n\n    - fields 以 `clean_tpex_field_name` 清洗後**完全相等**比對必要欄(各恰一次),欄數須 17;\n      列長須 17 —— 任一不符 → schema_error。\n    - 收盤 `\'----\'`／不可解析／≤0 → 該股無收盤(缺值,⛔ 不退去相鄰欄);最高或最低不可解析、或\n      `最低 ≤ 收盤 ≤ 最高` 不成立 → 該股缺值並計數。\n    - 單位守衛:有成交(成交股數>0 且 成交金額>0 且 高低可解析)列中,\n      `成交金額/成交股數 ∈ [最低×(1−tol), 最高×(1+tol)]` 成立率 < 門檻(或 0 列可驗)→ unit_error。\n    """\n    names = [clean_tpex_field_name(f) for f in fields]\n    if len(names) != TPEX_CLOSE_N_FIELDS:\n        return "schema_error", f"fields {len(names)} 欄 ≠ {TPEX_CLOSE_N_FIELDS}:{names}", {}\n    idx = {}\n    for col in TPEX_CLOSE_REQUIRED_COLS:\n        hits = [i for i, n in enumerate(names) if n == col]\n        if len(hits) != 1:\n            return "schema_error", f"必要欄 {col!r} 命中 {len(hits)} 次(清洗後 fields={names})", {}\n        idx[col] = hits[0]\n    bad_len = [i for i, row in enumerate(data)\n               if not isinstance(row, (list, tuple)) or len(row) != TPEX_CLOSE_N_FIELDS]\n    if bad_len:\n        return ("schema_error",\n                f"{len(bad_len)} 列長度≠{TPEX_CLOSE_N_FIELDS}(首例第 {bad_len[0]} 列)", {})\n    out: dict = {}\n    n_no_close = n_hl_bad = n_unit_ok = n_unit_chk = 0\n    tol = TPEX_CLOSE_VWAP_REL_TOL\n    for row in data:\n        code = str(row[idx[TPEX_CLOSE_COL_CODE]]).strip()\n        close = parse_tpex_price(row[idx[TPEX_CLOSE_COL_CLOSE]])\n        hi = parse_tpex_price(row[idx[TPEX_CLOSE_COL_HIGH]])\n        lo = parse_tpex_price(row[idx[TPEX_CLOSE_COL_LOW]])\n        vol = parse_tpex_price(row[idx[TPEX_CLOSE_COL_VOLUME]])\n        amt = parse_tpex_price(row[idx[TPEX_CLOSE_COL_AMOUNT]])\n        if hi is not None and lo is not None and vol and amt and vol > 0 and amt > 0:\n            n_unit_chk += 1\n            if lo * (1 - tol) <= amt / vol <= hi * (1 + tol):\n                n_unit_ok += 1\n        if not code or close is None or close <= 0:\n            n_no_close += 1\n            continue\n        if hi is None or lo is None or not (lo <= close <= hi):\n            n_hl_bad += 1\n            continue\n        out[code] = close\n    if n_hl_bad:\n        print(f"[TPEX close] ⚠️ {ds} 最高/最低不可解析或 最低≤收盤≤最高 不成立 {n_hl_bad} 列 → 該股缺值")\n    if n_unit_chk == 0:\n        return "unit_error", "無任何有成交列可驗單位(成交金額/成交股數)", {}\n    ratio = n_unit_ok / n_unit_chk\n    if ratio < TPEX_CLOSE_UNIT_GUARD_MIN_PASS_RATIO:\n        return ("unit_error", f"成交金額/成交股數 ∈ [最低,最高] 成立率 {ratio:.1%} "\n                f"({n_unit_ok}/{n_unit_chk}) < {TPEX_CLOSE_UNIT_GUARD_MIN_PASS_RATIO:.0%}", {})\n    if not out:\n        return "parse_zero", f"有 {len(data)} 列但解析 0 筆有效收盤", {}\n    print(f"[TPEX close] {ds}: 無收盤 {n_no_close} 列(缺值)、單位守衛 {n_unit_ok}/{n_unit_chk}")\n    return "ok", "", out\n\n\ndef fetch_tpex_close_day(ds: str) -> dict:\n',
         '\ndef fetch_tpex_close_day(ds: str) -> dict:\n'),
        ('\n    批 Z41(客戶 Q-z27＝A 受控遷移):來源改為櫃買中心官方新網站「上櫃股票每日收盤行情(不含定價)」\n    JSON(`afterTrading/otc?type=EW`,西元 `YYYY/MM/DD`)。舊 RWD php 交易日回 `totalCount=0` 空表\n    (探針實測)已不可用。守衛(任一不過 → 非 ok、回 {}):轉址 /errors、非 JSON、stat、日期回聲\n    (頂層 YYYYMMDD + tables[0] 民國)、title 以「上櫃股票每日收盤行情」開頭、fields 清洗後完全相等定位\n    (17 欄)、列長、逐列 最低≤收盤≤最高、整表單位守衛。收盤 `----`/不可解析 → 該股缺值(⛔ 不退相鄰欄)。\n    外幣交易 ETF(代號第六碼 K/C)收盤**照原值保留**於 L1;板塊金額換算的幣別排除在 L2\n    (`src/compute/sector_flow.compute_sector_daily_net`)。\n    批 Z39:各分支記 `_TPEX_CLOSE_DIAG[ds]`;非 ok 分支印洗過的 body 前 500 字。\n    """\n',
         '\n    來源:櫃買「上櫃股票每日收盤行情(不含定價)」RWD php(帶 ROC date,可回補歷史)。\n    aaData 每列:[代號, 名稱, 收盤, 漲跌, 開盤, 最高, 最低, 成交股數, 成交金額, ...]。\n    收盤欄位以「代號右側第一個有效數值」動態定位(勿硬編),避免版本欄序差異。\n    假日/無資料 → aaData 空 → 回 {}(§1 自然排除)。\n    批 Z39:各分支記 `_TPEX_CLOSE_DIAG[ds]`;「解析 0 筆」與例外分支印洗過的 body 前 500 字。\n    """\n'),
        ('    try:\n        r = _fetch(\n',
         '    try:\n        dt = _dt.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))\n        roc_date = f"{gregorian_to_roc_year(dt.year)}/{dt.month:02d}/{dt.day:02d}"\n        r = _fetch(\n'),
        ('        r = _fetch(\n            TPEX_CLOSE_URL,\n            params={"date": tpex_query_date(ds), "type": "EW", "id": "",\n                    "response": "json"},\n            timeout=20,\n',
         '        r = _fetch(\n            "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/"\n            "stk_wn1430_result.php",\n            params={"l": "zh-tw", "d": roc_date, "o": "json"},\n            timeout=20,\n'),
        ('            headers={**_HDR_JSON, "Referer": "https://www.tpex.org.tw/"})\n        if r is None:\n            return _tpex_close_fail(ds, "http_none", None, "fetch 回 None")\n        if getattr(r, "status_code", 0) != 200:\n            return _tpex_close_fail(ds, "http_error", r, f"HTTP={getattr(r, \'status_code\', None)}")\n        if tpex_redirected_to_error(r):\n            return _tpex_close_fail(ds, "redirect_error", r,\n                                    f"被轉往官方錯誤頁 url={getattr(r, \'url\', None)!r}")\n        try:\n',
         '            headers={**_HDR_JSON, "Referer": "https://www.tpex.org.tw/"})\n        if r is None or getattr(r, "status_code", 0) != 200:\n            _TPEX_CLOSE_DIAG[ds] = "http_none" if r is None else "http_error"\n            print(f"[TPEX close] {ds} HTTP={getattr(r, \'status_code\', \'None\')}")\n            return {}\n        try:\n'),
        ('        except ValueError as e:\n            return _tpex_close_fail(ds, "json_error", r, f"{type(e).__name__}: {e}")\n        # tables[0].date 探針未記錄是否存在 → 有就必須＝民國請求日、沒有不臆測(頂層回聲仍強制)\n        status, why, t0 = check_tpex_envelope(j, ds, title_prefix=TPEX_CLOSE_TITLE_PREFIX,\n                                              require_table_date=TPEX_CLOSE_REQUIRE_TABLE_DATE)\n        if status != "ok":\n            return _tpex_close_fail(ds, status, r, why)\n        status, why, out = _parse_tpex_close_rows(ds, list(t0.get("fields") or []),\n                                                  t0["data"])\n        if status != "ok":\n            return _tpex_close_fail(ds, status, r, why)\n        _TPEX_CLOSE_DIAG[ds] = "ok"\n        print(f"[TPEX close] {ds} ({tpex_roc_date(ds)}): {len(out)} 檔")\n        return out\n',
         '        except ValueError as e:\n            # 批 Z39:非 JSON 單獨記狀態;回傳 / log 前綴同原 except 分支\n            _TPEX_CLOSE_DIAG[ds] = "json_error"\n            print(f"[TPEX close] {ds} 失敗: {type(e).__name__}: {e} "\n                  f"body[:500]={scrubbed_body_head(r)!r}")\n            return {}\n        rows = j.get("aaData") or j.get("data") or []\n        out: dict = {}\n        for row in rows:\n            if not isinstance(row, (list, tuple)) or len(row) < 3:\n                continue\n            code = str(row[0]).strip()\n            if not code or not code[0].isdigit():\n                continue\n            # 收盤 = 代號、名稱之後的第一個有效數值(通常 index 2)\n            close = None\n            for idx in range(2, min(len(row), 6)):\n                close = _to_float(row[idx])\n                if close is not None:\n                    break\n            if code and close is not None and close > 0:\n                out[code] = close\n        if not out:\n            _TPEX_CLOSE_DIAG[ds] = "parse_zero" if rows else "empty"\n            print(f"[TPEX close] {ds} ({roc_date}) 解析 0 筆 "\n                  f"body[:500]={scrubbed_body_head(r)!r}")\n        else:\n            _TPEX_CLOSE_DIAG[ds] = "ok"\n            print(f"[TPEX close] {ds} ({roc_date}): {len(out)} 檔")\n        return out\n'),
        ('    except Exception as e:\n        return _tpex_close_fail(ds, "exception", r, f"{type(e).__name__}: {e}")\n\n',
         '    except Exception as e:\n        _TPEX_CLOSE_DIAG[ds] = "exception"\n        _body = f" body[:500]={scrubbed_body_head(r)!r}" if r is not None else ""\n        print(f"[TPEX close] {ds} 失敗: {type(e).__name__}: {e}{_body}")\n        return {}\n\n'),
    ),
}

#: 基底 `f0a32a3b` 原始檔 sha256（`git show f0a32a3b:<檔> | sha256sum` 實算；寫死以免測試依賴 git）
#: （`_CLOSE` 在 `7de354e8` 與 `f0a32a3b` 逐字相同；`_INST` 於 `f0a32a3b` 含 Z40 跟進二，sha 已改為該檔實算值。）
Z41_BASE_SHA = {
    _INST: "f0ab333ec30ed75539b1ae37acd4898c9b561e80f4e15dffdf44a607d952f472",
    _CLOSE: "edccacc8d6703497b297c0a7ca5d25063fbcad56504c2602a8cd5103d27e4d2d",
}
_SEQ = [0]


def z41_revert(rel: str, code: str) -> str:
    """現行原始碼 → 本批之前（`f0a32a3b`）原始碼（無 pair 的檔原樣）。舊批次還原鏈串接用。"""
    for new, old in Z41_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def _exec(rel: str, code: str, tag: str):
    _SEQ[0] += 1
    path = _ROOT / rel
    name = f"_z41_{tag}_{_SEQ[0]}"
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
def z41_pre_module(rel: str):
    """本批之前的模組（只把本批改動換回 `f0a32a3b` 寫法）。"""
    return _exec(rel, z41_revert(rel, (_ROOT / rel).read_text(encoding="utf-8")), "pre")


@pytest.mark.parametrize("rel", sorted(Z41_BASE_SHA))
def test_reverted_source_equals_base_file(rel):
    """還原體逐字 ＝ 基底 `f0a32a3b` 檔 ⇒ 下方「修前」對照跑的是真修前碼。"""
    code = z41_revert(rel, (_ROOT / rel).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z41_BASE_SHA[rel]


def test_older_batch_chains_include_z41():
    """Z39／Z40 的還原鏈已串接本批（否則它們的 base-sha 自證會對 L1 兩檔轉紅）。"""
    from tests import test_batch_z39 as Z39
    from tests import test_batch_z40 as Z40
    for rel in (_INST, _CLOSE):
        code = Z39.z39_revert(rel, (_ROOT / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z39.Z39_BASE_SHA[rel]
    code = Z40.z40_revert_for(_INST, (_ROOT / _INST).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z40.Z40_BASE_SHA[_INST]


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案
# ══════════════════════════════════════════════════════════════════════════
import scripts.update_sector_flow as U  # noqa: E402
import shared.tpex_schema as TS  # noqa: E402
import src.data.core.data_loader_inst_fetchers as ifx  # noqa: E402
import src.data.stock.market_close_fetcher as mcf  # noqa: E402
from shared.http_diag import scrub_session_values, scrubbed_body_head  # noqa: E402
from shared.sector_flow_thresholds import (  # noqa: E402
    SECTOR_FLOW_TWSE_ONLY_NOTE,
    is_foreign_ccy_code,
)
from src.compute.sector_flow import compute_sector_daily_net  # noqa: E402

_DS = "20261008"
_ROC = "115/10/08"

# ── 法人：fields 24 欄原文 + 三列真實列原文（探針 2026-10-08）──────────────────
INST_FIELDS = ["代號", "名稱"] + ["買進股數", "賣出股數", "買賣超股數"] * 7 + ["三大法人買賣超股數合計"]
_REAL = {
    "6488": ("環球晶", "6,053,408|7,354,566|-1,301,158|0|0|0|6,053,408|7,354,566|-1,301,158|51,100|"
                     "1,040,000|-988,900|169,000|108,695|60,305|733,542|789,597|-56,055|902,542|"
                     "898,292|4,250|-2,285,808"),
    "5347": ("世界", "5,849,814|4,763,068|1,086,746|0|0|0|5,849,814|4,763,068|1,086,746|359,000|"
                    "1,001,000|-642,000|9,000|16,000|-7,000|91,957|67,564|24,393|100,957|83,564|"
                    "17,393|462,139"),
    "8299": ("群聯", "693,766|941,594|-247,828|0|0|0|693,766|941,594|-247,828|28,359|200|28,159|"
                    "7,200|10,104|-2,904|75,933|71,665|4,268|83,133|81,769|1,364|-218,305"),
}
#: 期望輸出（張）＝ round(外資 idx4／投信 idx13／自營商 idx22 ÷ 1000, 1)
#: 批 Z41 修正（QA L1）：與上市 T86 同規則 `round(v/1000, 1)`（修前不捨入：-1301.158／4.25…）。
#: 註：4.25 → 4.2（Python round 半數取偶，T86 同一規則同一結果）。
_EXPECT = {
    "6488": {"外資": -1301.2, "投信": -988.9, "自營商": 4.2},
    "5347": {"外資": 1086.7, "投信": -642.0, "自營商": 17.4},
    "8299": {"外資": -247.8, "投信": 28.2, "自營商": 1.4},
}


def _real_rows():
    return [[c, n] + v.split("|") for c, (n, v) in _REAL.items()]


def _fmt(n: int) -> str:
    return f"{n:,}"


def _tp_row(code, g1=(5_000, 1_000), g2=(0, 0), g4=(300, 100), g5=(20, 10), g6=(7, 2),
            name="測"):
    """合成列（恆等式全成立）：G3＝G1＋G2、G7＝G5＋G6、T＝G1超＋G4超＋G7超。"""
    def grp(b, s):
        return [b, s, b - s]
    G1, G2, G4, G5, G6 = (grp(*g) for g in (g1, g2, g4, g5, g6))
    G3 = [a + b for a, b in zip(G1, G2)]
    G7 = [a + b for a, b in zip(G5, G6)]
    T = G1[2] + G4[2] + G7[2]
    return [code, name] + [_fmt(x) for x in G1 + G2 + G3 + G4 + G5 + G6 + G7 + [T]]


def _inst_payload(rows=None, *, ds=_DS, roc=_ROC, fields=None, title="三大法人買賣明細資訊",
                  stat="ok", total=None, column_num=25):
    rows = _real_rows() if rows is None else rows
    return {"columnNum": column_num,
            "tables": [{"title": title, "date": roc,
                        "totalCount": len(rows) if total is None else total,
                        "fields": list(INST_FIELDS if fields is None else fields),
                        "data": [list(r) for r in rows]}, {}],
            "template": "x", "date": ds, "stat": stat}


class _Hist:
    def __init__(self, url, location):
        self.url, self.headers = url, {"Location": location}


class _Resp:
    def __init__(self, payload=None, *, url="https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade",
                 history=(), raise_json=False, text="{}", status=200):
        self._p, self._raise = payload, raise_json
        self.url, self.history, self.text, self.status_code = url, list(history), text, status

    def json(self):
        if self._raise:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._p


@pytest.fixture
def tp(monkeypatch):
    """隔離 TPEx 進程快取；`tp(resp_or_callable)` 設 `_fetch_url_dl` 回傳；回傳呼叫紀錄 list。"""
    calls: list = []

    def _set(resp, mod=ifx):
        monkeypatch.setattr(mod, "_TPEX_DAY_CACHE", {})
        monkeypatch.setattr(mod, "_TPEX_FAIL_TS", {})
        monkeypatch.setattr(mod, "_TPEX_DAY_DIAG", {})

        def _f(url, params=None, **k):
            calls.append((url, dict(params or {})))
            return resp() if callable(resp) else resp
        monkeypatch.setattr(mod, "_fetch_url_dl", _f)
        return calls
    return _set


# ══════════════════════════════════════════════════════════════════════════
# 1. 法人 parser：真實列 → 官方口徑（與 FinMind／上市 T86 一致）
# ══════════════════════════════════════════════════════════════════════════
class TestInstRealRows:
    def test_real_rows_official_basis(self, tp):
        calls = tp(_Resp(_inst_payload()))
        got = ifx._get_tpex_day(_DS)
        assert ifx.get_tpex_day_status(_DS) == "ok"
        assert set(got) == set(_EXPECT)
        for code, exp in _EXPECT.items():
            for k, v in exp.items():
                assert got[code][k] == pytest.approx(v, abs=1e-9), (code, k)
        assert _DS in ifx._TPEX_DAY_CACHE and _DS not in ifx._TPEX_FAIL_TS
        url, params = calls[0]
        assert url == "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"
        assert params == {"type": "Daily", "sect": "EW", "date": "2026/10/08", "id": "",
                          "response": "json"}

    def test_matches_finmind_basis(self):
        """FinMind 口徑（探針 10 檔×3 天 100% 一致）：Foreign_Investor＝idx2/3、Foreign_Dealer_Self＝idx5/6、
        Investment_Trust＝idx11/12、Dealer_self＝idx14/15、Dealer_Hedging＝idx17/18 → `_normalize_inst_pivot`
        （Z40）後與 TPEx parser 輸出逐值相等。"""
        _st, _w, got = ifx._parse_tpex_inst_rows(_DS, _real_rows())
        assert _st == "ok"
        for code, (_n, v) in _REAL.items():
            x = [None, None] + [int(s.replace(",", "")) for s in v.split("|")]
            raw = pd.DataFrame([
                {"date": "2026-10-08", "name": nm, "buy": x[b], "sell": x[s]}
                for nm, b, s in (("Foreign_Investor", 2, 3), ("Foreign_Dealer_Self", 5, 6),
                                 ("Investment_Trust", 11, 12), ("Dealer_self", 14, 15),
                                 ("Dealer_Hedging", 17, 18))])
            pv = ifx._normalize_inst_pivot(raw).iloc[0]
            for k in ("外資", "投信", "自營商"):     # FinMind pivot 不捨入 → 同規則捨入後逐值相等
                assert round(pv[k], 1) == pytest.approx(got[code][k], abs=1e-9), (code, k)

    def test_same_basis_as_twse_t86(self, monkeypatch, tp):
        """同一檔假想股，上市 T86（Z40）與上櫃新 parser 輸出同口徑、同單位（張）。"""
        from tests.test_batch_z38 import FIELDS_NOW
        f, fd, t, dsf, dh = 1_234_500, 3_000, -200_000, 50_000, -20_000
        t86_row = ["9999", "假想", "0", "0", _fmt(f), "0", "0", _fmt(fd), "0", "0", _fmt(t),
                   _fmt(dsf + dh), "0", "0", _fmt(dsf), "0", "0", _fmt(dh), _fmt(f + t + dsf + dh)]
        g1b, g1s = 2_000_000, 2_000_000 - f
        tpex_row = _tp_row("9999", g1=(g1b, g1s), g2=(fd, 0), g4=(0, -t), g5=(dsf, 0), g6=(0, -dh))
        tp(lambda: None)

        def _f(url, params=None, **k):
            if "twse" in url:
                return _Resp({"stat": "OK", "fields": FIELDS_NOW, "data": [t86_row]})
            return _Resp(_inst_payload([tpex_row]))
        monkeypatch.setattr(ifx, "_T86_DAY_CACHE", {})
        monkeypatch.setattr(ifx, "_T86_FAIL_TS", {})
        monkeypatch.setattr(ifx, "_fetch_url_dl", _f)
        a, b = ifx._get_t86_day(_DS)["9999"], ifx._get_tpex_day(_DS)["9999"]
        assert a == b == {"外資": 1234.5, "投信": -200.0, "自營商": 30.0}

    @pytest.mark.parametrize("shares", [0, 1, 49, 50, 51, 149, 150, 250, 350, 4_250, -4_250,
                                        -1_301_158, 1_086_746, 17_393, 1_364, 999_950, -50])
    def test_lots_same_rule_as_t86(self, monkeypatch, shares):
        """批 Z41 修正（QA L1）：上櫃 `_tpex_lots` 與上市 `_get_t86_day` 逐值相同（含 .x5 邊界）。"""
        from tests.test_batch_z38 import FIELDS_NOW
        row = ["9999", "假想", "0", "0", _fmt(shares), "0", "0", "0", "0", "0", _fmt(shares),
               _fmt(shares), "0", "0", _fmt(shares), "0", "0", "0", _fmt(3 * shares)]
        monkeypatch.setattr(ifx, "_T86_DAY_CACHE", {})
        monkeypatch.setattr(ifx, "_T86_FAIL_TS", {})
        monkeypatch.setattr(ifx, "_fetch_url_dl", lambda *a, **k: _Resp(
            {"stat": "OK", "fields": FIELDS_NOW, "data": [row]}))
        t86 = ifx._get_t86_day(_DS)["9999"]
        assert t86["外資"] == ifx._tpex_lots(shares)
        assert t86["投信"] == ifx._tpex_lots(shares)

    def test_mutant_lots_unrounded(self, tp):
        M = _mut(_INST, [("    return float('nan') if shares is None else round(shares / 1000, 1)\n",
                          "    return float('nan') if shares is None else shares / 1000\n")])
        _got, _st = _status_of(tp, _Resp(_inst_payload()), M)
        assert _got["6488"]["外資"] == pytest.approx(-1301.158)    # 修前精度 ≠ 上市

    def test_codes_kept_as_strings(self, tp):
        rows = [_tp_row(" 00687C "), _tp_row("00411A"), _tp_row("006201")]
        tp(_Resp(_inst_payload(rows)))
        assert set(ifx._get_tpex_day(_DS)) == {"00687C", "00411A", "006201"}

    @pytest.mark.parametrize("cn", [25, 24, 3, None, "abc"])
    def test_column_num_not_used(self, tp, cn):
        tp(_Resp(_inst_payload(column_num=cn)))
        assert set(ifx._get_tpex_day(_DS)) == set(_EXPECT)
        assert ifx.get_tpex_day_status(_DS) == "ok"


# ══════════════════════════════════════════════════════════════════════════
# 2. 法人守衛（每條一測 + 突變）
# ══════════════════════════════════════════════════════════════════════════
def _status_of(tp, resp, mod=ifx):
    tp(resp, mod)
    got = mod._get_tpex_day(_DS)
    return got, mod.get_tpex_day_status(_DS)


def _assert_fail(tp, resp, status, mod=ifx):
    got, st = _status_of(tp, resp, mod)
    assert got == {} and st == status
    assert _DS not in mod._TPEX_DAY_CACHE, "非 ok 不得進永久快取"
    assert _DS in mod._TPEX_FAIL_TS, "非 ok 走短 TTL 負快取"


def _envelope_mut(pairs):
    """突變 L0 `check_tpex_envelope`，回傳替身函式（monkeypatch 進 ifx / mcf）。"""
    return _mut(_SCHEMA, pairs, "env").check_tpex_envelope


class TestInstGuards:
    def test_redirect_url(self, tp):
        _assert_fail(tp, _Resp(_inst_payload(), url="https://www.tpex.org.tw/errors"),
                     "redirect_error")

    def test_redirect_history(self, tp):
        h = _Hist("https://www.tpex.org.tw/web/stock/3insti/daily_report/3itrade_hedge_result.php",
                  "https://www.tpex.org.tw/errors")
        _assert_fail(tp, _Resp(_inst_payload(), url="https://www.tpex.org.tw/x", history=[h]),
                     "redirect_error")

    def test_mutant_redirect_guard_removed(self, tp, monkeypatch):
        monkeypatch.setattr(ifx, "tpex_redirected_to_error", lambda r: False)
        h = _Hist("https://old", "/errors")
        _got, st = _status_of(tp, _Resp(_inst_payload(), history=[h]))
        assert st == "ok"     # 拔掉守衛 ⇒ 轉址到錯誤頁卻被當成功

    def test_non_json(self, tp):
        _assert_fail(tp, _Resp(raise_json=True, text="<html>404</html>"), "json_error")

    def test_http_none(self, tp):
        _assert_fail(tp, None, "http_none")

    def test_stat_not_ok(self, tp, monkeypatch):
        _assert_fail(tp, _Resp(_inst_payload(stat="fail")), "schema_error")
        monkeypatch.setattr(ifx, "check_tpex_envelope", _envelope_mut([(
            '    if j.get("stat") != TPEX_STAT_OK:\n', '    if False:\n')]))
        assert _status_of(tp, _Resp(_inst_payload(stat="fail")))[1] == "ok"

    @pytest.mark.parametrize("kw", [dict(ds="20261007"), dict(roc="115/10/07"),
                                    dict(ds="20261007", roc="115/10/07")],
                             ids=["top-fallback", "table-fallback", "both-prev-day"])
    def test_date_echo_mismatch(self, tp, kw):
        _assert_fail(tp, _Resp(_inst_payload(**kw)), "schema_error")

    def test_mutant_date_echo_removed(self, tp, monkeypatch):
        monkeypatch.setattr(ifx, "check_tpex_envelope", _envelope_mut([
            ('    if str(j.get("date", "")).strip() != ds:\n', '    if False:\n'),
            ('    if (require_table_date or "date" in t0) and \\\n', '    if False and \\\n')]))
        got, st = _status_of(tp, _Resp(_inst_payload(ds="20261007", roc="115/10/07")))
        assert st == "ok" and got     # 回退前一交易日的資料被當成當日 = 修前風險

    def test_inst_table_date_required(self, tp):
        p = _inst_payload()
        del p["tables"][0]["date"]
        _assert_fail(tp, _Resp(p), "schema_error")     # 法人表 tables[0].date 探針實測存在 → 必須

    def test_title_mismatch(self, tp, monkeypatch):
        _assert_fail(tp, _Resp(_inst_payload(title="三大法人買賣金額彙總表")), "schema_error")
        monkeypatch.setattr(ifx, "check_tpex_envelope", _envelope_mut([(
            '    if title_exact is not None and title != title_exact:\n', '    if False:\n')]))
        assert _status_of(tp, _Resp(_inst_payload(title="別的表")))[1] == "ok"

    @pytest.mark.parametrize("fields", [
        INST_FIELDS[:-1], INST_FIELDS + ["多一欄"],
        INST_FIELDS[:2] + ["買進金額"] + INST_FIELDS[3:],
        INST_FIELDS[:23] + ["三大法人買賣超股數"]],
        ids=["少一欄", "多一欄", "欄名變動", "合計欄名變動"])
    def test_fields_not_exact(self, tp, fields):
        _assert_fail(tp, _Resp(_inst_payload(fields=fields)), "schema_error")

    def test_fields_whitespace_noise_ok(self, tp):
        tp(_Resp(_inst_payload(fields=[f" {f} " for f in INST_FIELDS])))
        assert set(ifx._get_tpex_day(_DS)) == set(_EXPECT)

    def test_mutant_fields_check_removed(self, tp):
        M = _mut(_INST, [("        if fields != TPEX_INST_FIELDS:\n", "        if False:\n")])
        flds = INST_FIELDS[:2] + ["買進金額"] + INST_FIELDS[3:]
        _got, st = _status_of(tp, _Resp(_inst_payload(fields=flds)), M)
        assert st == "ok"

    def test_row_length(self, tp):
        rows = _real_rows()
        rows[1] = rows[1][:-1]
        _assert_fail(tp, _Resp(_inst_payload(rows)), "schema_error")

    @pytest.mark.parametrize("col,label", [(4, "G1 買−賣≠超"), (13, "G4"), (19, "G6"), (23, "T")])
    def test_identity_failed(self, tp, col, label):
        rows = _real_rows()
        v = int(rows[0][col].replace(",", ""))
        rows[0][col] = _fmt(v + 1)
        _assert_fail(tp, _Resp(_inst_payload(rows)), "identity_failed")

    def test_identity_g1_g2_g3(self, tp):
        rows = [_tp_row("1111", g2=(1_000, 0))]
        rows[0][8] = _fmt(int(rows[0][8].replace(",", "")) + 1)     # G3 買 ≠ G1 買 + G2 買
        rows[0][10] = _fmt(int(rows[0][10].replace(",", "")) + 1)   # 讓 G3 自身 買−賣＝超 仍成立
        _assert_fail(tp, _Resp(_inst_payload(rows)), "identity_failed")

    def test_identity_g5_g6_g7(self, tp):
        rows = [_tp_row("1111")]
        rows[0][21] = _fmt(int(rows[0][21].replace(",", "")) - 1)   # G7 賣 ≠ G5 賣 + G6 賣
        rows[0][22] = _fmt(int(rows[0][22].replace(",", "")) + 1)   # G7 自身 買−賣＝超 仍成立
        rows[0][23] = _fmt(int(rows[0][23].replace(",", "")) + 1)   # T 跟著 G7 超
        _assert_fail(tp, _Resp(_inst_payload(rows)), "identity_failed")

    @staticmethod
    def _swapped_g1_g3(g2=(1_500, 500)):
        """G2 非零的一列，G1（不含）與 G3（含）欄位整組對調（官方表頭對調／欄序漂移的情境）。"""
        row = _tp_row("2222", g1=(10_000, 4_000), g2=g2)
        row[2:5], row[8:11] = row[8:11], row[2:5]
        return row

    def test_g2_nonzero_swap_detected(self, tp):
        _assert_fail(tp, _Resp(_inst_payload([self._swapped_g1_g3()])), "identity_failed")

    def test_g2_gross_only_swap_only_g1g2g3_detects(self, tp):
        """G2 買賣非零但淨額 0 ⇒ G1 超＝G3 超、T 恆等式抓不到，只有逐列 G1＋G2＝G3（買／賣欄）抓得到。"""
        row = self._swapped_g1_g3(g2=(500, 500))
        _assert_fail(tp, _Resp(_inst_payload([row])), "identity_failed")
        M = _mut(_INST, [("            if v[g1[k]] + v[g2[k]] != v[g3[k]]:\n", "            if False:\n")])
        assert _status_of(tp, _Resp(_inst_payload([row])), M)[1] == "ok"

    def test_mutant_g1g2g3_and_total_removed_wrong_foreign(self, tp):
        M = _mut(_INST, [("            if v[g1[k]] + v[g2[k]] != v[g3[k]]:\n", "            if False:\n"),
                         ("        if v[TPEX_IDX_TOTAL_NET] != v[g1[2]] + v[g4[2]] + v[g7[2]]:\n",
                          "        if False:\n")])
        got, st = _status_of(tp, _Resp(_inst_payload([self._swapped_g1_g3()])), M)
        # 兩條都拔 ⇒ 對調的表通過、外資被讀成「含外資自營商」7000 股＝7 張（正確應為 6 張）
        assert st == "ok" and got["2222"]["外資"] == pytest.approx(7.0)

    def test_g2_nonzero_ok_warns(self, tp, capsys):
        tp(_Resp(_inst_payload([_tp_row("2222", g1=(10_000, 4_000), g2=(1_500, 500))])))
        got = ifx._get_tpex_day(_DS)
        assert got["2222"]["外資"] == pytest.approx(6.0)        # G1 超（不含外資自營商）
        assert "外資自營商(G2)非零 1 列" in capsys.readouterr().out

    def test_invalid_row_ratio_parse_error(self, tp):
        rows = _real_rows()
        rows[0][9] = "N/A"
        _assert_fail(tp, _Resp(_inst_payload(rows)), "parse_error")   # 1/3 > 1%

    def _many(self, n=150):
        return [_tp_row(f"{1000 + i}") for i in range(n)]

    @staticmethod
    def _all_nan(d):
        return all(math.isnan(d[k]) for k in ("外資", "投信", "自營商"))

    def test_invalid_row_below_ratio_is_nan_not_zero(self, tp, capsys):
        """批 Z41 修正（QA M1）：不可解析列 → 該代號三分項 NaN（不省略、不當 0）。"""
        rows = self._many()
        rows[0][5] = "--"           # G2 買（真值 0）不可解析 → 該股缺值（不得當 0）
        tp(_Resp(_inst_payload(rows)))
        got = ifx._get_tpex_day(_DS)
        assert ifx.get_tpex_day_status(_DS) == "ok"
        assert len(got) == 150 and self._all_nan(got["1000"])
        assert not self._all_nan(got["1001"])
        assert "不可解析/重複代號列 1/150" in capsys.readouterr().out

    def test_mutant_unparsable_as_zero(self, tp, monkeypatch):
        S = _mut(_SCHEMA, [("    return int(s) if _INT_RE.match(s) else None\n",
                            "    return int(s) if _INT_RE.match(s) else 0\n")])
        monkeypatch.setattr(ifx, "parse_tpex_int", S.parse_tpex_int)
        rows = self._many()
        rows[0][5] = "--"
        tp(_Resp(_inst_payload(rows)))
        assert not self._all_nan(ifx._get_tpex_day(_DS)["1000"])   # 髒值當 0 ⇒ 缺值被冒充成有值

    def test_mutant_invalid_rows_omitted(self, tp):
        """修前（QA M1 前）寫法：無效列整檔省略 ⇒ L2 看不到缺值、當 0 貢獻。"""
        M = _mut(_INST, [("    for c in nan_codes:\n        day_data[c] = dict(_TPEX_NAN_ROW)\n", "")])
        rows = self._many()
        rows[0][5] = "--"
        got, _st = _status_of(tp, _Resp(_inst_payload(rows)), M)
        assert "1000" not in got

    def test_duplicate_code_is_nan(self, tp):
        rows = self._many(300)
        rows[1][0] = rows[0][0]          # 代號重複 → 兩列皆不可信（2/300 ≤ 1%）→ 該代號 NaN
        tp(_Resp(_inst_payload(rows)))
        got = ifx._get_tpex_day(_DS)
        assert ifx.get_tpex_day_status(_DS) == "ok" and len(got) == 299
        assert self._all_nan(got["1000"])

    def test_nan_reaches_l2_missing_counts(self, tp, monkeypatch):
        """無效列 NaN 一路到 L2：O1 遮罩讓該板塊三分項 NaN，`n_missing_*` 計數 1（不是 0 貢獻）。"""
        import tests.test_batch_z39 as Z39
        rows = self._many()
        rows[0][5] = "--"
        tp(_Resp(_inst_payload(rows)))
        tpex = ifx._get_tpex_day(_DS)
        day = dict(t86={"2330": {"外資": 1.0, "投信": 0.0, "自營商": 0.0}}, tpex=tpex,
                   tpex_status="ok", tpex_close_status="ok", twse_close={"2330": 100.0},
                   tpex_close={c: 10.0 for c in tpex})
        Z39._install(monkeypatch, U, {_DS: day})
        inst, price, _d = U._collect_days([pd.Timestamp(_DS).date()])
        imap = {c: "上櫃測試" for c in tpex} | {"2330": "上市測試"}
        sd, cov = compute_sector_daily_net(inst, price, imap)
        assert cov["n_missing_foreign_stock_days"] == 1
        otc = sd[sd["sector"] == "上櫃測試"].iloc[0]
        assert math.isnan(otc["foreign_yi"]) and math.isnan(otc["net_amt_yi"])

    def test_total_count_inconsistent(self, tp):
        """批 Z41 修正（QA L2）：totalCount ≠ len(data) → schema_error（防分頁／截斷）。"""
        _assert_fail(tp, _Resp(_inst_payload(total=0)), "schema_error")
        _assert_fail(tp, _Resp(_inst_payload([], total=5)), "schema_error")
        _assert_fail(tp, _Resp(_inst_payload(total=4)), "schema_error")
        _assert_fail(tp, _Resp(_inst_payload(total=2)), "schema_error")
        _assert_fail(tp, _Resp(_inst_payload(total="2")), "schema_error")
        tp(_Resp(_inst_payload(total="3")))
        assert ifx._get_tpex_day(_DS) and ifx.get_tpex_day_status(_DS) == "ok"

    def test_mutant_total_count_check_removed(self, tp, monkeypatch):
        monkeypatch.setattr(ifx, "check_tpex_envelope", _envelope_mut([(
            "    if tc_i is not None and tc_i != len(data):\n", "    if False:\n")]))
        assert _status_of(tp, _Resp(_inst_payload(total=900)))[1] == "ok"   # 截斷被靜默接受

    # ── 批 Z41 修正（QA M2）恆等式分級 ──────────────────────────────────────
    def test_data_guard_below_ratio_row_nan(self, tp, capsys):
        rows = self._many()
        rows[3][13] = _fmt(int(rows[3][13].replace(",", "")) + 1)    # G4 買−賣≠超（資料守衛）
        tp(_Resp(_inst_payload(rows)))
        got = ifx._get_tpex_day(_DS)
        assert ifx.get_tpex_day_status(_DS) == "ok"
        assert self._all_nan(got["1003"]) and not self._all_nan(got["1004"])
        assert "資料守衛" in capsys.readouterr().out

    @pytest.mark.parametrize("col", [4, 13, 19, 22, 23], ids=["G1", "G4", "G6", "G7", "T"])
    def test_data_guard_above_ratio_identity_failed(self, tp, col):
        rows = self._many()
        for i in (0, 1):                                           # 2/150 > 1%
            rows[i][col] = _fmt(int(rows[i][col].replace(",", "")) + 1)
        _assert_fail(tp, _Resp(_inst_payload(rows)), "identity_failed")

    def test_mutant_data_guard_ratio_removed(self, tp):
        M = _mut(_INST, [("        if len(data_fail_codes) / len(data) > TPEX_INST_MAX_IDENTITY_FAIL_ROW_RATIO:\n",
                          "        if False:\n")])
        rows = self._many()
        for i in range(10):
            rows[i][13] = _fmt(int(rows[i][13].replace(",", "")) + 1)
        assert _status_of(tp, _Resp(_inst_payload(rows)), M)[1] == "ok"

    def test_mutant_data_guard_rows_not_nan(self, tp):
        M = _mut(_INST, [("            data_fail_codes.append(f'{code}:{bad}')\n            nan_codes.add(code)\n",
                          "            data_fail_codes.append(f'{code}:{bad}')\n")])
        rows = self._many()
        rows[3][13] = _fmt(int(rows[3][13].replace(",", "")) + 1)
        got, _st = _status_of(tp, _Resp(_inst_payload(rows)), M)
        assert not self._all_nan(got["1003"])                    # 錯的列被當成有效值採用

    def test_semantic_guard_single_row_fails_whole_day(self, tp):
        """G1＋G2＝G3 不成立即使只有 1/150 列 → 整日 identity_failed（不受 1% 寬限）。"""
        rows = self._many()
        rows[0][8] = _fmt(int(rows[0][8].replace(",", "")) + 1)      # G3 買 ≠ G1 買 + G2 買
        rows[0][10] = _fmt(int(rows[0][10].replace(",", "")) + 1)    # G3 自身 買−賣＝超 仍成立
        _assert_fail(tp, _Resp(_inst_payload(rows)), "identity_failed")

    def test_mutant_semantic_guard_downgraded(self, tp):
        M = _mut(_INST, [("    if sem_fails:\n", "    if False:\n")])
        rows = self._many()
        rows[0][8] = _fmt(int(rows[0][8].replace(",", "")) + 1)
        rows[0][10] = _fmt(int(rows[0][10].replace(",", "")) + 1)
        assert _status_of(tp, _Resp(_inst_payload(rows)), M)[1] == "ok"   # 對調證據被當成單列髒資料

    def test_exception(self, tp):
        _assert_fail(tp, _Resp(["not", "a", "dict"]), "schema_error")

        class _Boom(_Resp):
            def json(self):
                raise RuntimeError("boom")
        _assert_fail(tp, _Boom(), "exception")


_SECRET = "SECRETTOKEN0123456789abcdef"
_LEAKY_BODY = (f"<html>token={_SECRET} proxy=http://px:S3cretPw@10.0.0.9:3128 "
               f'Cookie: SESS=c00kieval {{"sessionid": "jsonsess"}} ' + "x" * 3000 + "</html>")
_LEAKS = (_SECRET, "S3cretPw", "c00kieval", "jsonsess")


class TestFailLogScrubbed:
    """批 Z41 修正（QA L5）：現行碼的失敗 log 印的 body 已過 `scrubbed_body_head`（含 token／proxy 密碼／Cookie）。"""

    def test_inst_fail_log_scrubbed(self, tp, capsys):
        _assert_fail(tp, _Resp(raise_json=True, text=_LEAKY_BODY), "json_error")
        out = capsys.readouterr().out
        assert "body[:500]=" in out and not any(x in out for x in _LEAKS)

    def test_mutant_inst_raw_body(self, tp, capsys):
        M = _mut(_INST, [("    print(f'[TPEx] {ds} status={status} body[:500]={scrubbed_body_head(r)!r}')\n",
                          "    print(f'[TPEx] {ds} status={status} body[:500]={r.text[:500]!r}')\n")])
        _status_of(tp, _Resp(raise_json=True, text=_LEAKY_BODY), M)
        assert _SECRET in capsys.readouterr().out

    def test_close_fail_log_scrubbed(self, cl, capsys):
        assert _close(cl, _Resp(raise_json=True, text=_LEAKY_BODY)) == ({}, "json_error")
        out = capsys.readouterr().out
        assert "body[:500]=" in out and not any(x in out for x in _LEAKS)

    def test_mutant_close_raw_body(self, cl, capsys):
        M = _mut(_CLOSE, [('    _body = f" body[:500]={scrubbed_body_head(r)!r}" if r is not None else ""\n',
                           '    _body = f" body[:500]={r.text[:500]!r}" if r is not None else ""\n')])
        _close(cl, _Resp(raise_json=True, text=_LEAKY_BODY), M)
        assert _SECRET in capsys.readouterr().out


class TestInstEmptyAndCache:
    def test_empty_is_not_ok_and_not_permanently_cached(self, tp, monkeypatch):
        calls = tp(_Resp(_inst_payload([], total=0)))
        assert ifx._get_tpex_day(_DS) == {}
        assert ifx.get_tpex_day_status(_DS) == "empty"
        assert _DS not in ifx._TPEX_DAY_CACHE and _DS in ifx._TPEX_FAIL_TS
        ifx._get_tpex_day(_DS)
        assert len(calls) == 1                          # 短 TTL 內不重打（不轟炸）
        ifx._TPEX_FAIL_TS[_DS] = time.time() - 10_000   # TTL 過期
        monkeypatch.setattr(ifx, "_fetch_url_dl", lambda *a, **k: _Resp(_inst_payload()))
        assert set(ifx._get_tpex_day(_DS)) == set(_EXPECT)   # 來源恢復 → 可重抓

    def test_mutant_empty_permanently_cached(self, tp, monkeypatch):
        """修前語意（空表永久快取）⇒ 來源恢復後同進程永遠拿不到資料。"""
        M = _mut(_INST, [("    _TPEX_FAIL_TS[ds] = _t_tpf.time()\n", "    _TPEX_DAY_CACHE[ds] = {}\n")])
        tp(_Resp(_inst_payload([], total=0)), M)
        M._get_tpex_day(_DS)
        monkeypatch.setattr(M, "_fetch_url_dl", lambda *a, **k: _Resp(_inst_payload()))
        assert M._get_tpex_day(_DS) == {}

    @pytest.mark.parametrize("ds,roc", [("20261009", "115/10/09"), ("20261010", "115/10/10"),
                                        ("20261231", "115/12/31")])
    def test_non_trading_day_shape(self, tp, ds, roc):
        """探針：非交易日 stat=ok、date 回聲＝請求日、totalCount=0、data=[] → empty（非 ok），
        不回退前一交易日；休市與否由 cron 以 TWSE 同日判定。"""
        tp(_Resp(_inst_payload([], ds=ds, roc=roc, total=0)))
        assert ifx._get_tpex_day(ds) == {} and ifx.get_tpex_day_status(ds) == "empty"

    def test_ok_cached_permanently(self, tp, monkeypatch):
        calls = tp(_Resp(_inst_payload()))
        ifx._get_tpex_day(_DS)
        monkeypatch.setattr(ifx, "_fetch_url_dl", lambda *a, **k: pytest.fail("不該重打"))
        assert set(ifx._get_tpex_day(_DS)) == set(_EXPECT) and len(calls) == 1

    def test_statuses_registered(self):
        assert set(ifx.TPEX_DAY_STATUSES) == {
            "ok", "empty", "http_none", "redirect_error", "json_error", "schema_error",
            "identity_failed", "parse_error", "exception"}


class TestFallbackNewSemantics:
    """選股網 `_fetch_tpex_inst_fallback`：程式碼不變，但 `_get_tpex_day` 語意改了 ——
    空表不再永久快取 ⇒ 不再被算成「有回答」。"""

    def _df(self):
        import datetime as _dt
        base = _dt.date.today()
        return pd.DataFrame({"date": [base - _dt.timedelta(days=i) for i in range(20)]})

    def test_all_empty_is_failure_not_answer(self, tp):
        tp(lambda: _Resp(_inst_payload([], total=0)))
        failed: dict = {}
        out = ifx._fetch_tpex_inst_fallback("6488", self._df(), failed=failed)
        assert "tpex" in failed and "外資" not in out.columns

    def test_pre_z41_counted_empty_as_answer(self, tp):
        """對照：修前模組（舊端點 aaData 空）永久快取空 ⇒ 被算成「有回答」⇒ 故障被說成「這檔沒資料」。"""
        P = z41_pre_module(_INST)
        tp(lambda: _Resp({"aaData": []}), P)
        failed: dict = {}
        P._fetch_tpex_inst_fallback("6488", self._df(), failed=failed)
        assert "tpex" not in failed

    def test_ok_day_merges(self, tp, monkeypatch):
        import datetime as _dt
        d = _dt.date.today()
        while d.weekday() >= 5:
            d -= _dt.timedelta(days=1)
        ds = d.strftime("%Y%m%d")
        roc = TS.tpex_roc_date(ds)
        tp(lambda: None)

        def _f(url, params=None, **k):
            q = params["date"].replace("/", "")
            if q == ds:
                return _Resp(_inst_payload(ds=ds, roc=roc))
            return _Resp(_inst_payload([], ds=q, roc=TS.tpex_roc_date(q), total=0))
        monkeypatch.setattr(ifx, "_fetch_url_dl", _f)
        failed: dict = {}
        out = ifx._fetch_tpex_inst_fallback("6488", pd.DataFrame({"date": [d]}), failed=failed)
        assert not failed
        assert out.loc[0, "外資"] == pytest.approx(-1301.2)
        assert out.loc[0, "主力合計"] == pytest.approx(-1301.2 - 988.9 + 4.2)


# ══════════════════════════════════════════════════════════════════════════
# 3. 收盤 parser
# ══════════════════════════════════════════════════════════════════════════
CLOSE_FIELDS = ['代號', '名稱', '收盤 ', '漲跌', '開盤 ', '最高 ', '最低', '成交股數  ', ' 成交金額(元)',
                ' 成交筆數 ', '最後買價', '最後買量<br>(張數)', '最後賣價', '最後賣量<br>(張數)',
                '發行股數 ', '次日漲停價 ', '次日跌停價']


def _crow(code, close, high, low, vol, amt, chg="0.00", opn=None, name="名"):
    opn = close if opn is None else opn
    return [code, name, close, chg, opn, high, low, vol, amt, "100", close, "1", close, "1",
            "1,000,000", "1.00", "1.00"]


def _close_rows():
    return [
        _crow("6488", "1,130.00", "1,195.00", "1,095.00", "2,500,000", "2,850,000,000", "-45.00"),
        _crow("5347", "186.50", "190.00", "183.00", "10,000,000", "1,870,000,000"),
        _crow("8299", "2,060.00", "2,100.00", "2,020.00", "1,000,000", "2,065,000,000", "除息"),
        _crow("00687C", "35.10", "35.50", "35.00", "100,000", "3,520,000"),
        _crow("9998", "----", "----", "----", "0", "0", "---", opn="12.00"),
    ]


def _close_payload(rows=None, *, ds=_DS, roc=_ROC, fields=None,
                   title="上櫃股票每日收盤行情(不含定價)", stat="ok"):
    rows = _close_rows() if rows is None else rows
    return {"tables": [{"title": title, "date": roc, "subtitle": "x",
                        "category": "所有證券(不含權證、牛熊證)",
                        "fields": list(CLOSE_FIELDS if fields is None else fields),
                        "data": [list(r) for r in rows], "totalCount": len(rows),
                        "notes": ["ETF證券代號第六碼為K、C者，表示該ETF以外幣交易。"]}],
            "date": ds, "flagField": "張數", "stat": stat}


@pytest.fixture
def cl(monkeypatch):
    calls: list = []

    def _set(resp, mod=mcf):
        monkeypatch.setattr(mod, "_TPEX_CLOSE_DIAG", {})

        def _f(url, params=None, **k):
            calls.append((url, dict(params or {})))
            return resp
        monkeypatch.setattr(mod, "_fetch", _f)
        return calls
    return _set


def _close(cl, resp, mod=mcf):
    cl(resp, mod)
    return mod.fetch_tpex_close_day(_DS), mod.get_tpex_close_status(_DS)


class TestClose:
    def test_real_fields_noise_and_values(self, cl):
        calls = cl(_Resp(_close_payload()))
        out = mcf.fetch_tpex_close_day(_DS)
        assert mcf.get_tpex_close_status(_DS) == "ok"
        assert out == {"6488": 1130.0, "5347": 186.5, "8299": 2060.0, "00687C": 35.1}
        assert calls[0][0] == "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc"
        assert calls[0][1] == {"date": "2026/10/08", "type": "EW", "id": "", "response": "json"}

    def test_field_cleaning(self):
        assert [TS.clean_tpex_field_name(f) for f in CLOSE_FIELDS][:9] == [
            "代號", "名稱", "收盤", "漲跌", "開盤", "最高", "最低", "成交股數", "成交金額(元)"]
        assert TS.clean_tpex_field_name("最後買量<br>(張數)") == "最後買量(張數)"

    def test_dash_close_is_missing_not_adjacent(self, cl):
        out, st = _close(cl, _Resp(_close_payload()))
        assert st == "ok" and "9998" not in out      # 開盤 12.00 不得被拿來當收盤

    def test_pre_z41_fell_back_to_adjacent_column(self, monkeypatch):
        """對照：修前「代號右側第一個有效數值」寫法遇 `----` 收盤會拿到開盤價。"""
        P = z41_pre_module(_CLOSE)
        rows = [r[:] for r in _close_rows()]
        rows[-1][3] = "----"     # 漲跌也無效 → 修前一路往右找到 開盤 12.00
        resp = _Resp({"aaData": rows})
        monkeypatch.setattr(P, "_fetch", lambda *a, **k: resp)
        assert P.fetch_tpex_close_day(_DS).get("9998") == 12.0

    def test_high_low_guard(self, cl, capsys):
        rows = _close_rows()
        rows[1] = _crow("5347", "196.50", "190.00", "183.00", "10,000,000", "1,870,000,000")
        out, st = _close(cl, _Resp(_close_payload(rows)))
        assert st == "ok" and "5347" not in out
        assert "最低≤收盤≤最高 不成立 1 列" in capsys.readouterr().out

    def test_mutant_high_low_guard_removed(self, cl):
        M = _mut(_CLOSE, [("        if hi is None or lo is None or not (lo <= close <= hi):\n",
                           "        if False:\n")])
        rows = _close_rows()
        rows[1] = _crow("5347", "196.50", "190.00", "183.00", "10,000,000", "1,870,000,000")
        out, _st = _close(cl, _Resp(_close_payload(rows)), M)
        assert out["5347"] == 196.5

    def test_unit_guard_thousand_yuan(self, cl):
        rows = [r[:] for r in _close_rows()]
        for r in rows:
            amt = int(r[8].replace(",", ""))
            r[8] = _fmt(amt // 1000)          # 金額單位誤為千元 → 均價差 1000 倍
        out, st = _close(cl, _Resp(_close_payload(rows)))
        assert st == "unit_error" and out == {}

    def test_mutant_unit_guard_removed(self, cl):
        M = _mut(_CLOSE, [("    if ratio < TPEX_CLOSE_UNIT_GUARD_MIN_PASS_RATIO:\n", "    if False:\n")])
        rows = [r[:] for r in _close_rows()]
        for r in rows:
            r[8] = _fmt(int(r[8].replace(",", "")) // 1000)
        out, st = _close(cl, _Resp(_close_payload(rows)), M)
        assert st == "ok" and out

    def test_unit_guard_no_traded_rows(self, cl):
        out, st = _close(cl, _Resp(_close_payload([_close_rows()[-1]])))
        assert st == "unit_error" and out == {}

    @pytest.mark.parametrize("fields", [
        CLOSE_FIELDS[:-1], CLOSE_FIELDS + ["x"],
        [("收盤價" if f == "收盤 " else f) for f in CLOSE_FIELDS],
        [("最高價" if f == "最高 " else f) for f in CLOSE_FIELDS],
        [("收盤" if f == "開盤 " else f) for f in CLOSE_FIELDS]],
        ids=["16欄", "18欄", "收盤改名", "最高改名", "收盤重複"])
    def test_fields_schema(self, cl, fields):
        out, st = _close(cl, _Resp(_close_payload(fields=fields)))
        assert st == "schema_error" and out == {}

    def test_row_length(self, cl):
        rows = _close_rows()
        rows[0] = rows[0][:-1]
        assert _close(cl, _Resp(_close_payload(rows))) == ({}, "schema_error")

    @pytest.mark.parametrize("kw,status", [
        (dict(ds="20261007"), "schema_error"), (dict(roc="115/10/07"), "schema_error"),
        (dict(stat="fail"), "schema_error"), (dict(title="上櫃股票行情"), "schema_error")])
    def test_envelope(self, cl, kw, status):
        assert _close(cl, _Resp(_close_payload(**kw))) == ({}, status)

    def test_total_count_mismatch(self, cl):
        """批 Z41 修正（QA L2）：收盤表 totalCount（若有）≠ 列數 → schema_error；沒有 totalCount 不臆測。"""
        p = _close_payload()
        p["tables"][0]["totalCount"] = len(_close_rows()) + 1
        assert _close(cl, _Resp(p)) == ({}, "schema_error")
        p2 = _close_payload()
        del p2["tables"][0]["totalCount"]
        assert _close(cl, _Resp(p2))[1] == "ok"

    def test_table_date_absent_ok_present_must_match(self, cl):
        """收盤表探針未記錄 `tables[0].date` 是否存在 → 沒有就不臆測（頂層回聲仍強制）、有就必須相符。"""
        p = _close_payload()
        del p["tables"][0]["date"]
        assert _close(cl, _Resp(p))[1] == "ok"
        p2 = _close_payload(roc="115/10/07")
        assert _close(cl, _Resp(p2)) == ({}, "schema_error")
        p3 = _close_payload(ds="20261007")
        del p3["tables"][0]["date"]
        assert _close(cl, _Resp(p3)) == ({}, "schema_error")

    def test_redirect_and_json(self, cl):
        assert _close(cl, _Resp(_close_payload(), url="https://www.tpex.org.tw/errors")) \
            == ({}, "redirect_error")
        assert _close(cl, _Resp(raise_json=True)) == ({}, "json_error")
        assert _close(cl, None) == ({}, "http_none")
        assert _close(cl, _Resp({}, status=500)) == ({}, "http_error")

    def test_empty(self, cl):
        assert _close(cl, _Resp(_close_payload([]))) == ({}, "empty")


# ══════════════════════════════════════════════════════════════════════════
# 4. 外幣 ETF（L2 排除、計數；L1 照原值保留）
# ══════════════════════════════════════════════════════════════════════════
class TestForeignCcy:
    @pytest.mark.parametrize("code,exp", [
        ("00687C", True), ("00636K", True), ("00625K", True), ("0061XM", True), ("00700S", True),
        (" 00687c ", True), ("00981A", False), ("006208", False), ("2330", False),
        ("03001C", False), ("02001S", False), ("12345K", False), ("0061XS", True),
        ("6488", False), ("00411A", False), ("", False)])
    def test_is_foreign_ccy_code(self, code, exp):
        assert is_foreign_ccy_code(code) is exp

    def _inputs(self):
        day = pd.Timestamp("2026-10-08")
        inst = pd.DataFrame([
            {"date": day, "stock_id": "6488", "foreign_lots": -1301.158, "trust_lots": -988.9,
             "dealer_lots": 4.25},
            {"date": day, "stock_id": "00687C", "foreign_lots": 100.0, "trust_lots": 0.0,
             "dealer_lots": 0.0},
            {"date": day, "stock_id": "00636K", "foreign_lots": 50.0, "trust_lots": 0.0,
             "dealer_lots": 0.0}])
        price = pd.DataFrame([{"date": day, "stock_id": c, "close": p}
                              for c, p in (("6488", 1130.0), ("00687C", 35.1), ("00636K", 20.0))])
        return inst, price, {"6488": "半導體業", "00687C": "上櫃ETF", "00636K": "ETF"}

    def test_excluded_and_counted(self, caplog):
        sd, cov = compute_sector_daily_net(*self._inputs())
        assert set(sd["sector"]) == {"半導體業"}
        assert cov["n_excluded_foreign_ccy_stock_days"] == 2
        assert cov["n_stock_days_with_net"] == 1
        assert any("外幣交易 ETF" in r.getMessage() for r in caplog.records)
        r = sd.iloc[0]
        assert r["foreign_yi"] == pytest.approx(-1301.158 * 1000 * 1130.0 / 1e8)

    def test_key_present_on_empty(self):
        _sd, cov = compute_sector_daily_net(pd.DataFrame(), pd.DataFrame(), {})
        assert cov["n_excluded_foreign_ccy_stock_days"] == 0

    def test_mutant_exclusion_removed(self):
        M = _mut(_L2, [("    inst = inst[~_fx]\n", "")])
        sd, _cov = M.compute_sector_daily_net(*self._inputs())
        assert "上櫃ETF" in set(sd["sector"])        # 外幣收盤被當新台幣加總 = Level 1 單位錯誤

    def test_l1_keeps_foreign_ccy_close(self, cl):
        out, _st = _close(cl, _Resp(_close_payload()))
        assert out["00687C"] == 35.1       # L1 不動資料；排除只在 L2


# ══════════════════════════════════════════════════════════════════════════
# 5. 舊／新合理性比較（僅上市 vs 上市＋上櫃）
# ══════════════════════════════════════════════════════════════════════════
def _ticker_sector() -> dict:
    """真實 `data_cache/sector_flow/ticker_sector.json`（唯讀）取本測試用代號的產業別。"""
    m = json.loads((_ROOT / "data_cache/sector_flow/ticker_sector.json").read_text(encoding="utf-8"))
    return {c: m[c] for c in ("2330", "2317", "6488", "5347", "8299", "8446", "6180")}


def compare_twse_only_vs_combined(day_spec: dict, imap: dict) -> dict:
    """同一日：TPEx 失敗（僅上市）vs TPEx 成功（上市＋上櫃）兩種情境的板塊淨額（億）。"""
    import tests.test_batch_z39 as Z39
    out = {}
    for label, patch in (("twse_only", {"tpex_status": "empty"}), ("combined", {})):
        with pytest.MonkeyPatch.context() as mp:
            Z39._install(mp, U, {_DS: {**day_spec, **patch}})
            inst, price, _diag = U._collect_days([pd.Timestamp(_DS).date()])
        sd, _cov = compute_sector_daily_net(inst, price, imap)
        out[label] = dict(zip(sd["sector"], sd["net_amt_yi"]))
    return out


class TestOldNewComparison:
    def test_twse_unchanged_tpex_into_own_sector_pure_otc_new(self):
        imap = _ticker_sector()
        assert imap["8446"] == imap["6180"] == "文化創意業"
        v = lambda f, t, d: {"外資": f, "投信": t, "自營商": d}  # noqa: E731
        day = dict(
            t86={"2330": v(1000.0, 10.0, -5.0), "2317": v(-300.0, 0.0, 2.0)},
            tpex={"6488": v(*_EXPECT["6488"].values()), "5347": v(*_EXPECT["5347"].values()),
                  "8446": v(12.0, 0.0, 1.0), "6180": v(-3.0, 1.0, 0.0)},
            tpex_status="ok", tpex_close_status="ok",
            twse_close={"2330": 1200.0, "2317": 210.0},
            tpex_close={"6488": 1130.0, "5347": 186.5, "8446": 50.0, "6180": 120.0})
        r = compare_twse_only_vs_combined(day, imap)
        twse_only, comb = r["twse_only"], r["combined"]
        # 上市部分不變：只有上市股的板塊淨額完全相同
        assert comb[imap["2317"]] == pytest.approx(twse_only[imap["2317"]])
        # 上櫃股只進其產業板塊：半導體業差額 ＝ 6488＋5347 的金額
        _amt = lambda c, p: sum(day["tpex"][c].values()) * 1000 * p / 1e8  # noqa: E731
        assert comb["半導體業"] - twse_only["半導體業"] == pytest.approx(
            _amt("6488", 1130.0) + _amt("5347", 186.5))
        # 純上櫃產業新增
        assert "文化創意業" not in twse_only
        assert comb["文化創意業"] == pytest.approx(_amt("8446", 50.0) + _amt("6180", 120.0))
        assert set(comb) - set(twse_only) == {"文化創意業"}


# ══════════════════════════════════════════════════════════════════════════
# 6. R1 自動回補
# ══════════════════════════════════════════════════════════════════════════
_OLD_DATES = [d.date() for d in pd.bdate_range(end="2026-10-08", periods=18)]
_TODAY = pd.Timestamp("2026-10-12").date()      # 週一；新日期 10-09、10-12
_IMAP = {"2330": "半導體業", "2317": "其他電子業", "6488": "半導體業", "8446": "文化創意業"}


def _old_parquet(path, dates=_OLD_DATES, with_flag=False, flag=None):
    rows = []
    for d in dates:
        for sec in ("半導體業", "其他電子業", "舊殘留板塊"):
            rows.append({"date": pd.Timestamp(d), "sector": sec, "net_amt_yi": 1.0,
                         "foreign_yi": 1.0, "trust_yi": 0.0, "dealer_yi": 0.0, "n_stocks": 1,
                         "source": "TWSE:T86+MI_INDEX / TPEX:3itrade+otc_quotes",
                         "fetched_at": "old"})
    df = pd.DataFrame(rows)
    if with_flag:
        df["twse_ok"] = True
        df["tpex_ok"] = flag
    df.to_parquet(path, index=False)
    return df


def _good_day(tpex_ok=True):
    v = lambda f, t, d: {"外資": f, "投信": t, "自營商": d}  # noqa: E731
    return dict(t86={"2330": v(100.0, 1.0, 0.0), "2317": v(-5.0, 0.0, 0.0)},
                tpex={"6488": v(10.0, 0.0, 0.0), "8446": v(2.0, 0.0, 0.0)},
                tpex_status="ok" if tpex_ok else "empty",
                twse_close={"2330": 1000.0, "2317": 100.0},
                tpex_close={"6488": 500.0, "8446": 50.0} if tpex_ok else {},
                tpex_close_status="ok" if tpex_ok else "empty")


def _run(monkeypatch, mod, tmp_path, today, spec, imap=None, argv=()):
    import tests.test_batch_z39 as Z39
    Z39._install(monkeypatch, mod, spec)
    for k, f in (("CACHE_DIR", ""), ("PARQUET_PATH", "daily_net.parquet"),
                 ("BUBBLE_PATH", "bubble_latest.json"), ("META_PATH", "metadata.json"),
                 ("TICKER_SECTOR_PATH", "ticker_sector.json")):
        monkeypatch.setattr(mod, k, tmp_path / f if f else tmp_path)
    _m = dict(_IMAP) if imap is None else dict(imap)
    monkeypatch.setattr(mod, "fetch_industry_map_bulk", lambda: dict(_m))
    monkeypatch.setattr(mod, "_today", lambda: today)
    seen: list = []
    _orig = mod._collect_days
    monkeypatch.setattr(mod, "_collect_days", lambda days: (seen.append(list(days)), _orig(days))[1])
    rc = mod.main(list(argv))
    meta = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
    return rc, (seen[0] if seen else []), meta


def _all_days(tpex_ok=True):
    days = _OLD_DATES + [pd.Timestamp("2026-10-09").date(), _TODAY]
    return {d.strftime("%Y%m%d"): _good_day(tpex_ok) for d in days}


class TestBackfill:
    def test_candidates_include_old_na_days(self, tmp_path):
        old = _old_parquet(tmp_path / "p.parquet")
        assert U._tpex_backfill_days(old, _TODAY) == _OLD_DATES          # 18 日、無 tpex_ok 欄
        flagged = old.assign(tpex_ok=pd.array([pd.NA] * len(old), dtype="boolean"))
        assert U._tpex_backfill_days(flagged, _TODAY) == _OLD_DATES      # 有欄但 NA

    def test_only_not_true_days(self, tmp_path):
        old = _old_parquet(tmp_path / "p.parquet")
        old["tpex_ok"] = [d != pd.Timestamp(_OLD_DATES[3]) for d in old["date"]]
        assert U._tpex_backfill_days(old, _TODAY) == [_OLD_DATES[3]]

    def test_cap_25(self, tmp_path, monkeypatch):
        dates = [d.date() for d in pd.bdate_range(end="2026-10-08", periods=40)]
        old = _old_parquet(tmp_path / "p.parquet", dates)
        monkeypatch.setattr(U, "WINDOW_SIZE", 40)
        got = U._tpex_backfill_days(old, _TODAY)
        assert len(got) == U._TPEX_BACKFILL_MAX_DAYS == 25 and got == dates[-25:]

    def test_backfill_success_rewrites_days_and_caption_disappears(self, monkeypatch, tmp_path):
        _old_parquet(tmp_path / "daily_net.parquet")
        rc, seen, meta = _run(monkeypatch, U, tmp_path, _TODAY, _all_days())
        assert rc == 0 and set(_OLD_DATES) <= set(seen)
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        assert "舊殘留板塊" not in set(pq["sector"])                 # 先刪該日所有舊列
        assert pq["tpex_ok"].all() and pq["date"].nunique() == 20
        assert all("TPEX:insti/dailyTrade" in s for s in pq["source"])
        assert "文化創意業" in set(pq["sector"])                       # 純上櫃產業回補進來
        assert meta["backfilled_days"] == [d.strftime("%Y%m%d") for d in _OLD_DATES]
        assert meta["tpex_backfill"]["attempted_on"] == _TODAY.isoformat()
        bj = json.loads((tmp_path / "bubble_latest.json").read_text(encoding="utf-8"))
        assert bj["tpex_complete"] is True
        assert not any("僅含上市" in w for w in meta["warnings"])
        # UI：Z39 既有資料驅動判斷 → 「目前僅含上市資料」自動消失
        import src.data.sector_flow.reader as R
        import src.ui.tabs.tab_sector_flow as T
        import tests.test_batch_z39 as Z39
        monkeypatch.setattr(R, "BUBBLE_PATH", tmp_path / "bubble_latest.json")
        monkeypatch.setattr(R, "META_PATH", tmp_path / "metadata.json")
        monkeypatch.setattr(R, "TICKER_SECTOR_PATH", tmp_path / "ticker_sector.json")
        tpc = R.read_sector_flow_cache()["tpex_complete"]
        assert tpc is True
        fake = Z39._run_tab(monkeypatch, T, Z39._view(tpc))
        assert SECTOR_FLOW_TWSE_ONLY_NOTE not in fake.captions

    def test_mutant_no_delete_leaves_stale_sector(self, monkeypatch, tmp_path):
        M = _mut(_SCRIPT, [("        _base = existing[~_exd.isin(list(_new_dates)).to_numpy()]\n", "")])
        _old_parquet(tmp_path / "daily_net.parquet")
        _run(monkeypatch, M, tmp_path, _TODAY, _all_days())
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        assert "舊殘留板塊" in set(pq["sector"])       # 只靠 keep=last ⇒ 舊板塊列殘留

    def test_tpex_still_failing(self, monkeypatch, tmp_path):
        _old_parquet(tmp_path / "daily_net.parquet")
        spec = _all_days(tpex_ok=False)
        spec[_TODAY.strftime("%Y%m%d")]["t86"] = {}    # 今天 TWSE 未出 → unresolved（同日重跑會重抓）
        rc, seen, meta = _run(monkeypatch, U, tmp_path, _TODAY, spec)
        assert rc == 0 and set(_OLD_DATES) <= set(seen)
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        assert not pq["tpex_ok"].any()                         # 不得寫 tpex_ok=True
        assert meta["backfilled_days"] == []
        assert len(meta["tpex_backfill"]["still_twse_only"]) == 18
        bj = json.loads((tmp_path / "bubble_latest.json").read_text(encoding="utf-8"))
        assert bj["tpex_complete"] is False
        # 同日再跑：每日最多一次 → 不再回補（不轟炸）
        rc2, seen2, meta2 = _run(monkeypatch, U, tmp_path, _TODAY, spec)
        assert seen2 == [_TODAY]                        # 只重抓 unresolved 的今天
        assert meta2["tpex_backfill"]["skipped"] and meta2["tpex_backfill"]["attempted"] == []
        assert meta2["tpex_backfill"]["attempted_on"] == _TODAY.isoformat()
        # 隔天：再試一次
        nxt = pd.Timestamp("2026-10-13").date()
        spec = {**_all_days(tpex_ok=True), nxt.strftime("%Y%m%d"): _good_day()}
        _rc3, seen3, meta3 = _run(monkeypatch, U, tmp_path, nxt, spec)
        assert set(_OLD_DATES) <= set(seen3)
        assert set(meta3["backfilled_days"]) >= {d.strftime("%Y%m%d") for d in _OLD_DATES[-17:]}
        assert meta3["tpex_backfill"]["attempted_on"] == nxt.isoformat()

    def test_mutant_once_per_day_guard_removed(self, monkeypatch, tmp_path):
        M = _mut(_SCRIPT, [("    if _bf_cands and _bf_on == today.isoformat():\n", "    if False:\n")])
        _old_parquet(tmp_path / "daily_net.parquet")
        _run(monkeypatch, M, tmp_path, _TODAY, _all_days(tpex_ok=False))
        _rc, seen2, _m = _run(monkeypatch, M, tmp_path, _TODAY, _all_days(tpex_ok=False))
        assert set(_OLD_DATES) <= set(seen2)          # 同日重複轟炸

    def test_backfill_day_twse_fails_keeps_existing(self, monkeypatch, tmp_path):
        _old_parquet(tmp_path / "daily_net.parquet")
        spec = _all_days()
        bad = _OLD_DATES[5].strftime("%Y%m%d")
        spec[bad] = {**spec[bad], "t86": {}}           # 回補日這次 TWSE 失敗
        _rc, _seen, meta = _run(monkeypatch, U, tmp_path, _TODAY, spec)
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        kept = pq[pq["date"] == pd.Timestamp(_OLD_DATES[5])]
        assert set(kept["sector"]) == {"半導體業", "其他電子業", "舊殘留板塊"}   # 既有列不動
        assert bad not in meta["unresolved_days"]
        assert meta["tpex_backfill"]["kept_existing"] == [bad]
        bj = json.loads((tmp_path / "bubble_latest.json").read_text(encoding="utf-8"))
        assert bj["tpex_complete"] is False            # 該日仍非 True → 提示續留

    def test_no_existing_no_backfill(self):
        assert U._tpex_backfill_days(None, _TODAY) == []
        assert U._tpex_backfill_days(pd.DataFrame(), _TODAY) == []

    def test_already_complete_no_backfill(self, monkeypatch, tmp_path):
        _old_parquet(tmp_path / "daily_net.parquet", with_flag=True, flag=True)
        _rc, seen, meta = _run(monkeypatch, U, tmp_path, _TODAY, _all_days())
        assert not (set(_OLD_DATES) & set(seen))
        assert meta["tpex_backfill"]["candidates"] == []


def _prev_ticker_sector(tmp_path, n=100):
    m = {f"{1000 + i}": "某產業" for i in range(n)} | dict(_IMAP)
    (tmp_path / "ticker_sector.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return m


class TestIndustryMapGuard:
    """批 Z41 修正（QA H1）：產業別對映為空／縮水 > 20% → 禁止改寫任何既有日、回補全部跳過。"""

    def _old_rows(self, pq):
        return pq[pq["date"] <= pd.Timestamp(_OLD_DATES[-1])].sort_values(
            ["date", "sector"]).reset_index(drop=True)

    def test_qa_repro_empty_map_does_not_rewrite(self, monkeypatch, tmp_path):
        """QA 情境：TPEx 成功、產業別 {} → 既有 18 日不得被改寫成「未分類」並標 tpex_ok=True。"""
        before = _old_parquet(tmp_path / "daily_net.parquet")
        _prev_ticker_sector(tmp_path)
        rc, seen, meta = _run(monkeypatch, U, tmp_path, _TODAY, _all_days(), imap={})
        assert rc == 0 and not (set(_OLD_DATES) & set(seen))       # 回補全部跳過
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        old = self._old_rows(pq)
        exp = before.sort_values(["date", "sector"]).reset_index(drop=True)
        assert old[list(exp.columns)].astype(str).equals(exp.astype(str))   # 既有 18 日原封不動
        assert "tpex_ok" not in pq.columns or not pq.loc[
            pq["date"] <= pd.Timestamp(_OLD_DATES[-1]), "tpex_ok"].fillna(False).any()
        assert "產業別" in (meta["tpex_backfill"]["skipped"] or "")
        assert meta["tpex_backfill"]["attempted_on"] != _TODAY.isoformat()   # 明日再試
        assert meta["backfilled_days"] == []
        assert meta["last_error"] and "產業別" in meta["last_error"]
        assert any("產業別對映異常" in w for w in meta["warnings"])
        # 新日照寫（含 warning）
        assert pd.Timestamp(_TODAY) in set(pq["date"])
        assert json.loads((tmp_path / "ticker_sector.json").read_text(encoding="utf-8"))   # 上一份保留

    def test_mutant_guard_removed_rewrites_window(self, monkeypatch, tmp_path):
        M = _mut(_SCRIPT, [("    _ind_guard = _industry_map_guard(industry_map)\n",
                            "    _ind_guard = None\n")])
        _old_parquet(tmp_path / "daily_net.parquet")
        _prev_ticker_sector(tmp_path)
        _run(monkeypatch, M, tmp_path, _TODAY, _all_days(), imap={})
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        old = pq[pq["date"] <= pd.Timestamp(_OLD_DATES[-1])]
        assert set(old["sector"]) == {"未分類"} and old["tpex_ok"].all()   # QA H1 的錯誤鎖定

    def test_shrink_over_threshold_guarded(self, monkeypatch, tmp_path):
        _old_parquet(tmp_path / "daily_net.parquet")
        prev = _prev_ticker_sector(tmp_path, n=100)             # 104 檔
        shrunk = dict(list(prev.items())[:70])                 # 縮水 ~33%
        shrunk |= dict(_IMAP)
        rc, seen, meta = _run(monkeypatch, U, tmp_path, _TODAY, _all_days(), imap=shrunk)
        assert rc == 0 and not (set(_OLD_DATES) & set(seen))
        assert "縮水" in meta["last_error"]
        kept = json.loads((tmp_path / "ticker_sector.json").read_text(encoding="utf-8"))
        assert kept == prev                                     # 縮水版不覆寫上一份

    def test_shrink_within_threshold_backfills(self, monkeypatch, tmp_path):
        _old_parquet(tmp_path / "daily_net.parquet")
        prev = _prev_ticker_sector(tmp_path, n=100)
        ok_map = dict(list(prev.items())[:90]) | dict(_IMAP)   # 縮水 < 20%
        rc, seen, meta = _run(monkeypatch, U, tmp_path, _TODAY, _all_days(), imap=ok_map)
        assert set(_OLD_DATES) <= set(seen) and meta["last_error"] is None
        assert len(meta["backfilled_days"]) == 18

    def test_guard_function(self, monkeypatch, tmp_path):
        monkeypatch.setattr(U, "TICKER_SECTOR_PATH", tmp_path / "t.json")
        assert U._industry_map_guard({}) and U._industry_map_guard({"1": " "})
        assert U._industry_map_guard({"1": "A"}) is None          # 無上一份 → 只看是否為空
        (tmp_path / "t.json").write_text(json.dumps({str(i): "A" for i in range(10)}), encoding="utf-8")
        assert U._industry_map_guard({str(i): "A" for i in range(8)}) is None      # 縮 20% 不算超過
        assert U._industry_map_guard({str(i): "A" for i in range(7)})               # 縮 30%
        assert U.INDUSTRY_MAP_MAX_SHRINK_RATIO == 0.20

    def test_bootstrap_with_bad_map_keeps_existing(self, monkeypatch, tmp_path):
        before = _old_parquet(tmp_path / "daily_net.parquet")
        _prev_ticker_sector(tmp_path)
        import tests.test_batch_z39 as Z39
        Z39._install(monkeypatch, U, _all_days())
        for k, f in (("CACHE_DIR", ""), ("PARQUET_PATH", "daily_net.parquet"),
                     ("BUBBLE_PATH", "bubble_latest.json"), ("META_PATH", "metadata.json"),
                     ("TICKER_SECTOR_PATH", "ticker_sector.json")):
            monkeypatch.setattr(U, k, tmp_path / f if f else tmp_path)
        monkeypatch.setattr(U, "fetch_industry_map_bulk", lambda: {})
        monkeypatch.setattr(U, "_today", lambda: _TODAY)
        monkeypatch.setattr(U, "_candidate_trading_days",
                            lambda *a, **k: _OLD_DATES + [_TODAY])
        assert U.main(["--bootstrap"]) == 0
        pq = pd.read_parquet(tmp_path / "daily_net.parquet")
        old = self._old_rows(pq)
        exp = before.sort_values(["date", "sector"]).reset_index(drop=True)
        assert old[list(exp.columns)].astype(str).equals(exp.astype(str))


_NAN3 = {"外資": float("nan"), "投信": float("nan"), "自營商": float("nan")}


class TestN1FallbackAllNan:
    """批 Z41 修正二（QA N1）：M1 讓無效代號回三分項全 NaN；選股網 TPEx fallback 不得因此長出
    全 NaN 法人欄（→ `_inst_src='tpex'` → D2 `fillna(0)` → 籌碼卡顯示 0）。"""

    @staticmethod
    def _days(n=10):
        import datetime as _dt
        out, d = [], _dt.date.today()
        while len(out) < n:
            if d.weekday() < 5:
                out.append(d)
            d -= _dt.timedelta(days=1)
        return out

    def _install_days(self, monkeypatch, mod, per_day):
        """`per_day(date) -> {code: {...}}`；每天都當成 ok 日（進 `_TPEX_DAY_CACHE` ＝ 有回答）。"""
        cache: dict = {}
        monkeypatch.setattr(mod, "_TPEX_DAY_CACHE", cache)

        def _get(ds):
            import datetime as _dt
            d = _dt.datetime.strptime(ds, "%Y%m%d").date()
            cache[ds] = per_day(d)
            return cache[ds]
        monkeypatch.setattr(mod, "_get_tpex_day", _get)

    def test_all_nan_days_produce_no_columns(self, monkeypatch, capsys):
        self._install_days(monkeypatch, ifx, lambda d: {"6488": dict(_NAN3)})
        failed: dict = {}
        out = ifx._fetch_tpex_inst_fallback("6488", pd.DataFrame({"date": self._days(3)}),
                                            failed=failed)
        assert "外資" not in out.columns and not failed
        assert "三分項全 NaN" in capsys.readouterr().out

    def test_partial_nan_kept_as_nan(self, monkeypatch):
        days = self._days(3)
        part = {"外資": float("nan"), "投信": 1.0, "自營商": 2.0}
        self._install_days(monkeypatch, ifx, lambda d: {
            "6488": dict(part) if d == days[0] else
            (dict(_NAN3) if d == days[1] else {"外資": 5.0, "投信": 0.0, "自營商": 0.0})})
        out = ifx._fetch_tpex_inst_fallback("6488", pd.DataFrame({"date": days}))
        by = out.set_index("date")
        assert math.isnan(by.loc[days[0], "外資"]) and by.loc[days[0], "投信"] == 1.0
        assert math.isnan(by.loc[days[0], "主力合計"])
        assert math.isnan(by.loc[days[1], "外資"]) and math.isnan(by.loc[days[1], "投信"])
        assert by.loc[days[2], "外資"] == 5.0

    def _loader_df(self, monkeypatch, fallback_mod):
        """籌碼卡上游：`StockDataLoader.get_combined_data`（FinMind 掛、T86 有回答但無此檔、TPEx 全 NaN）。"""
        import src.data.core.data_loader as DL
        import tests.test_v2_silent_fail_b13_q5r2 as Q
        monkeypatch.setattr(DL, "_yf_dl", Q._yf_price_frame)
        monkeypatch.setattr(DL, "get_stock_name", lambda sid: "測試股")
        monkeypatch.setattr(DL, "_fetch_finmind_margin_raw", lambda sid, df, s: (df, "missing"))
        monkeypatch.setattr(DL, "_bps_dl", lambda: Q._FmSess(ConnectionError("proxy down")))
        monkeypatch.setattr(ifx, "_T86_DAY_CACHE", {})

        def _t86(ds):
            ifx._T86_DAY_CACHE[ds] = {}
            return {}
        monkeypatch.setattr(ifx, "_get_t86_day", _t86)
        self._install_days(monkeypatch, fallback_mod, lambda d: {"6488": dict(_NAN3)})
        monkeypatch.setattr(DL, "_fetch_tpex_inst_fallback", fallback_mod._fetch_tpex_inst_fallback)
        loader = DL.StockDataLoader.__new__(DL.StockDataLoader)
        loader.dl = None
        DL.StockDataLoader._get_combined_data_cached.clear()
        try:
            df, err, _ = loader.get_combined_data("6488", 180, True)
        finally:
            DL.StockDataLoader._get_combined_data_cached.clear()
        assert err is None
        return df

    def test_chips_upstream_missing_not_zero(self, monkeypatch):
        df = self._loader_df(monkeypatch, ifx)
        assert df.attrs["inst_src"] == "missing"
        assert not any(c in df.columns for c in ("外資", "投信", "自營商", "主力合計"))

    def test_mutant_skip_removed_shows_zero(self, monkeypatch):
        M = _mut(_INST, [("                    _n_all_nan += 1      # 批 Z41 修正二(QA N1):全 NaN = 該日此股無資料,不入 rows\n"
                          "                    continue\n", "                    pass\n")])
        df = self._loader_df(monkeypatch, M)
        assert df.attrs["inst_src"] == "tpex"
        assert (df["外資"] == 0).all()           # 「未取得」被 D2 補成 0 = QA N1 回歸


class TestR1IndustryOkBackfill:
    """批 Z41 修正二（QA R1）：產業別異常期間寫入的新日標 `industry_ok=False`，產業別恢復後自動重算。"""

    def test_backfill_days_industry_semantics(self, tmp_path):
        old = _old_parquet(tmp_path / "p.parquet", with_flag=True, flag=True)
        assert U._tpex_backfill_days(old, _TODAY) == []                  # 舊列無 industry_ok → 可信
        na = old.assign(industry_ok=pd.array([pd.NA] * len(old), dtype="boolean"))
        assert U._tpex_backfill_days(na, _TODAY) == []                   # NA → 可信（不無限回補）
        bad = old.assign(industry_ok=pd.array(
            [False if d == pd.Timestamp(_OLD_DATES[2]) else pd.NA for d in old["date"]],
            dtype="boolean"))
        assert U._tpex_backfill_days(bad, _TODAY) == [_OLD_DATES[2]]     # 只有明確 False

    def _two_runs(self, monkeypatch, mod, tmp_path):
        _old_parquet(tmp_path / "daily_net.parquet", with_flag=True, flag=True)
        _rc, _seen, meta1 = _run(monkeypatch, mod, tmp_path, _TODAY, _all_days(), imap={})
        pq1 = pd.read_parquet(tmp_path / "daily_net.parquet")
        nd = [pd.Timestamp("2026-10-09"), pd.Timestamp(_TODAY)]
        assert set(pq1.loc[pq1["date"].isin(nd), "sector"]) == {"未分類"}
        assert not pq1.loc[pq1["date"].isin(nd), "industry_ok"].any()
        assert any("20261009" in w and "產業別異常期間寫入日" in w for w in meta1["warnings"])
        nxt = pd.Timestamp("2026-10-13").date()
        spec = {**_all_days(), nxt.strftime("%Y%m%d"): _good_day()}
        _rc2, seen2, meta2 = _run(monkeypatch, mod, tmp_path, nxt, spec)    # 產業別恢復
        return pq1, seen2, meta2, pd.read_parquet(tmp_path / "daily_net.parquet"), nd

    def test_repro_recovers_next_day(self, monkeypatch, tmp_path):
        _pq1, seen2, meta2, pq2, nd = self._two_runs(monkeypatch, U, tmp_path)
        assert {d.date() for d in nd} <= set(seen2)
        assert not (set(_OLD_DATES) & set(seen2))        # 舊列（無欄）不被重抓
        re = pq2[pq2["date"].isin(nd)]
        assert "未分類" not in set(re["sector"]) and re["industry_ok"].all()
        assert {"半導體業", "文化創意業"} <= set(re["sector"])
        assert not any("產業別異常期間寫入日" in w for w in meta2["warnings"])
        assert pq2["date"].nunique() == 21 and meta2["last_error"] is None

    def test_mutant_industry_days_not_backfilled(self, monkeypatch, tmp_path):
        M = _mut(_SCRIPT, [("               if not bool(_all_ok.get(x, False)) or pd.Timestamp(x) in _ind_bad]\n",
                            "               if not bool(_all_ok.get(x, False))]\n")])
        _pq1, _seen2, _meta2, pq2, nd = self._two_runs(monkeypatch, M, tmp_path)
        assert set(pq2.loc[pq2["date"].isin(nd), "sector"]) == {"未分類"}   # 永久鎖住 = QA R1

    def test_mutant_flag_not_written(self, monkeypatch, tmp_path):
        M = _mut(_SCRIPT, [('    sector_daily["industry_ok"] = not bool(_ind_guard)\n', "")])
        _old_parquet(tmp_path / "daily_net.parquet", with_flag=True, flag=True)
        _run(monkeypatch, M, tmp_path, _TODAY, _all_days(), imap={})
        nxt = pd.Timestamp("2026-10-13").date()
        spec = {**_all_days(), nxt.strftime("%Y%m%d"): _good_day()}
        _rc, seen2, _m = _run(monkeypatch, M, tmp_path, nxt, spec)
        assert pd.Timestamp("2026-10-09").date() not in set(seen2)       # 沒旗標 ⇒ 不會被重算


class TestCollectDaysCloseStatus:
    def test_close_status_not_ok_blocks_tpex(self, monkeypatch):
        import tests.test_batch_z39 as Z39
        day = {**_good_day(), "tpex_close_status": "unit_error"}
        Z39._install(monkeypatch, U, {_DS: day})
        _i, _p, diag = U._collect_days([pd.Timestamp(_DS).date()])
        assert diag["per_day"][_DS]["tpex_ok"] is False


# ══════════════════════════════════════════════════════════════════════════
# 7. http_diag：JSON 帶引號 key 的 Cookie / session（Z39 QA 殘留缺口）
# ══════════════════════════════════════════════════════════════════════════
class TestJsonCookieScrub:
    @pytest.mark.parametrize("raw,secret", [
        ('{"Cookie": "a=b"}', "a=b"), ('{"sessionid":"zzz"}', "zzz"),
        ("{'Set-Cookie': ['SID=abc', 'tk=def']}", "SID=abc"), ('{"sid": 123456789}', "123456789"),
        ('{"JSESSIONID":"q\\"secretx","a":"b"}', "secretx"),
        ('{"headers": {"Cookie": "SID=abc; token=1", "Accept": "x"}}', "SID=abc"),
        ('{"PHPSESSID" : "phpzzz"}', "phpzzz")])
    def test_masked(self, raw, secret):
        out = scrub_session_values(raw)
        assert secret not in out and "***" in out

    @pytest.mark.parametrize("raw", ['{"cookie_policy": "ok"}', '{"considered":"y"}',
                                     '{"Accept": "x", "a": "b"}'])
    def test_non_secret_untouched(self, raw):
        assert scrub_session_values(raw) == raw

    def test_keeps_other_keys(self):
        assert scrub_session_values('{"sid": 12, "keep":"v"}') == '{"sid": "***", "keep":"v"}'

    def test_body_head_path(self):
        out = scrubbed_body_head(_Resp(text='{"stat":"ok","Cookie": "SESS=topsecret"}'))
        assert "topsecret" not in out

    @pytest.mark.parametrize("raw,expect", [
        ('{"Cookie": ["a", ["n"]], "k": 1}', '{"Cookie": "***", "k": 1}'),
        ('{"sid": {"x": 1}, "k": 2}', '{"sid": "***", "k": 2}'),
        ('{"sid": {"x": "}]", "y": [1, {"z": "q"}]}, "k": [3]}', '{"sid": "***", "k": [3]}'),
        ("{'Set-Cookie': [['a=b'], {'c': 'd'}], 'ok': True}", "{'Set-Cookie': \"***\", 'ok': True}"),
        ('[{"sessionid": {"a": [1, 2]}}, {"keep": 1}]', '[{"sessionid": "***"}, {"keep": 1}]'),
    ])
    def test_nested_values_fully_masked(self, raw, expect):
        """批 Z41 修正（QA L6）：巢狀陣列／物件整段遮，不外洩內層、不截壞外層結構。"""
        out = scrub_session_values(raw)
        assert out == expect
        if raw.startswith(("{\"", "[")):
            json.loads(out)

    def test_truncated_nested_value_masked_to_end(self):
        out = scrub_session_values('{"Cookie": ["a", ["topsecret"')
        assert "topsecret" not in out and out.endswith('"***"')

    @pytest.mark.parametrize("raw", [
        '{"sid":' + "[" * 20_000, '{"sid": "' + "a" * 20_000, '{"sid":' + '{"x":' * 4_000,
        '"sid":' * 4_000, '{"Cookie": "' + "\\" * 10_000, "x" * 20_000])
    def test_no_redos_linear(self, raw):
        t0 = time.perf_counter()
        scrub_session_values(raw)
        assert time.perf_counter() - t0 < 1.0

    def test_mutant_flat_regex_leaks_nested(self):
        """修前（QA L6 前）只遮不巢狀陣列：巢狀時遮不完整（外洩內層或截壞結構）。"""
        D = _mut(_DIAG, [("        vend = _json_value_end(text, vstart)\n",
                          "        vend = text.find(']', vstart) + 1 or len(text)\n")])
        out = D.scrub_session_values('{"Cookie": ["a", ["n"]], "k": 1}')
        assert out != '{"Cookie": "***", "k": 1}'

    def test_mutant_json_rule_removed(self):
        D = _mut(_DIAG, [("    text = _mask_json_secrets(text)\n", "")])
        assert "zzz" in D.scrub_session_values('{"sessionid":"zzz"}')


# ══════════════════════════════════════════════════════════════════════════
# 8. 登記 / 文件
# ══════════════════════════════════════════════════════════════════════════
def test_registry_and_doc_point_to_new_endpoint():
    from src.data.core.data_registry import DATA_REGISTRY
    e = [x for x in DATA_REGISTRY if x.get("name") == "OTC 三大法人"]
    assert len(e) == 1 and e[0]["endpoint"] == "/www/zh-tw/insti/dailyTrade"
    doc = (_ROOT / "DATASTATION.md").read_text(encoding="utf-8")
    assert "`/www/zh-tw/insti/dailyTrade`" in doc
    src = (_ROOT / _INST).read_text(encoding="utf-8") + (_ROOT / _CLOSE).read_text(encoding="utf-8")
    assert "3itrade_hedge_result.php'," not in src and "stk_wn1430_result.php" not in src
