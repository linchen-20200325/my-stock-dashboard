"""批 Z40 —— 法人口徑統一為官方口徑（客戶 2026-10-11 裁示 Q-z24＝A'、Q-z25＝A；基底 `ba470b9b`）。

官方口徑（TWSE BFI82U notes：「因外資自營商買賣金額已計入自營商買賣金額，故不納入三大法人買賣金額之合計數計算。」）：
- 外資 ＝ 外資及陸資（**不含**外資自營商）；
- 自營商 ＝ 自營商（自行買賣）＋ 自營商（避險）；
- 外資自營商**不再額外加到任何一類**（它已含在自營商內）；三大法人合計不含外資自營商項。
上市（TWSE T86／BFI82U）與 FinMind（上市櫃共用）口徑一致；TPEx `_get_tpex_day` 不在本批（另批 Z41 整個替換）。

本檔逐處守：
1. `daily_data_fetchers._parse_bfi82u_rows`：外資自營商列不再加進自營商（修前重複計算）。
2. `macro_fetch_orchestrator` FinMind 補救：外資只取 Foreign_Investor；自營商只取 Dealer_self＋Dealer_Hedging；
   Foreign_Dealer_Self／「外資自營商」排除於所有類別（含旗標）。
3. `nas_server._fetch_institutional`：自營商加總與外資退路都排除外資自營商。
4. `foreign_flow_fetcher.fetch_foreign_flow_series`：外資只取 Foreign_Investor（中文退路排除外資自營商）。
5. `scripts/update_macro_history.fetch_finmind_inst`：只取 Foreign_Investor；歷史不重抓，只做口徑標註
   （docstring／註解／列級 source）。
6. `data_loader_inst_fetchers._normalize_inst_pivot`：rename 前明確 drop 外資自營商欄。
7. `data_loader_inst_fetchers._get_t86_day`：欄名完全相等；自營商取「自營商買賣超股數」（自行＋避險）並逐列守衛；
   缺欄／髒值 → NaN（不回 0.0 假 0）；真 0 保持 0。

突變：`Z40_REVERT_PAIRS` 為「修後逐字 → 修前逐字」（每組在現行檔恰出現一次）；還原體逐字 ＝ 基底 `ba470b9b`
檔案（sha256 自證）。各核心修正另有單點突變（拔掉該處修正 ⇒ 對應行為斷言轉紅）。
舊批次 Z36 的還原鏈（`tests/test_batch_z36.py::z36_revert`）先串本批 pair 再還原 Z36（同 Z33 串 Z34 慣例）。
"""
from __future__ import annotations

import functools
import hashlib
import importlib.util
import pathlib
import sys
import types

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原 pair（先於任何 tests.* import 定義 —— tests/test_batch_z36.py 會回頭 import 本表）
# ══════════════════════════════════════════════════════════════════════════
_DDF = 'src/data/daily/daily_data_fetchers.py'
_ORCH = 'src/services/macro_fetch_orchestrator.py'
_NAS = 'src/data/proxy/nas_server.py'
_FFF = 'src/data/macro/foreign_flow_fetcher.py'
_UMH = 'scripts/update_macro_history.py'
_DLIF = 'src/data/core/data_loader_inst_fetchers.py'
_MCR = 'src/data/macro/macro_cache_reader.py'
_EXP = 'scripts/export_stock_db.py'

#: 修後逐字 → 修前逐字（每組在現行檔恰一處）。key ＝ repo 相對路徑。
Z40_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _DDF: (
        ('from shared.inst_labels import is_foreign_dealer_label  # 批 Z40 法人身分別判定 SSOT(L0)\n',
         ''),
        ("    # 📌 批 Z40（客戶 Q-z24＝A'）更正下段 Z36 註解的「加總值照舊」：自 Z40 起「外資自營商」列**不再**併入自營商加總\n    #   （官方口徑：已含在自營商自行＋避險內）；Z36 的自營觀測旗標判定本身不變。\n",
         ''),
        ("        elif is_foreign_dealer_label(_nm):\n            # 批 Z40（客戶 Q-z24＝A' 官方口徑）：「外資自營商」列已含在自營商（自行＋避險）內\n            #   （BFI82U notes：外資自營商買賣金額已計入自營商買賣金額）⇒ 不得再加進自營商（修前重複計算），\n            #   也不歸外資。明確略過並 log；`_seen`／Z36 自營觀測旗標語意不變（本列本就不算國內自營觀測）。\n            print(f'[三大法人/BFI82U] 略過「{_nm}」列 {_net} 億（官方口徑：已含在自營商自行＋避險內，不另計）')\n",
         ''),
    ),
    _ORCH: (
        ('from shared.inst_labels import (  # 批 Z40 法人身分別判定 SSOT(L0)\n    is_finmind_dealer, is_finmind_foreign_investor, is_foreign_dealer_label)\n',
         ''),
        ("                    # 批 Z40（客戶 Q-z24＝A' 官方口徑／Q-z25＝A）：列歸屬改走單一判定 `_fm_cat` ——\n                    #   外資 ＝ 只取 Foreign_Investor（中文相容：含「外資」且非外資自營商）；\n                    #   自營商 ＝ 只取 Dealer_self ＋ Dealer_Hedging（中文相容：含「自營」且不含「外資」）；\n                    #   Foreign_Dealer_Self／「外資自營商」（同時含 foreign 與 dealer 子字串）明確排除於所有類別\n                    #   （已含在自營商自行＋避險內；修前被 'foreign' 子字串歸進外資）。\n                    def _fm_cat(_n: str):\n                        if is_foreign_dealer_label(_n):\n                            return None\n                        if is_finmind_foreign_investor(_n) or '外資' in _n:\n                            return '外資'\n                        if 'investment_trust' in _n.lower() or '投信' in _n:\n                            return '投信'\n                        if is_finmind_dealer(_n) or ('自營' in _n and '外資' not in _n):\n                            return '自營'\n                        return None\n                    _fm_cats = _df_i['name'].astype(str).map(_fm_cat)\n                    _fm_fd_n = int(_df_i['name'].astype(str).map(is_foreign_dealer_label).sum())\n                    if _fm_fd_n:\n                        print(f'[FinMind-Inst] 略過外資自營商 {_fm_fd_n} 列（官方口徑：已含在自營商自行＋避險內，不另計）')\n                    _fm_foreign_rows = _fm_cats == '外資'\n",
         "                    _fm_foreign_rows = _df_i['name'].astype(str).map(\n                        lambda _n: 'foreign' in _n.lower() or '外資' in _n)\n"),
        ("                    _fm_trust_rows = _fm_cats == '投信'\n                    _fm_dealer_rows = _fm_cats == '自營'\n",
         "                    _fm_trust_rows = ~_fm_foreign_rows & _df_i['name'].astype(str).map(\n                        lambda _n: 'investment_trust' in _n.lower() or '投信' in _n)\n                    _fm_dealer_rows = ~_fm_foreign_rows & ~_fm_trust_rows & _df_i['name'].astype(str).map(\n                        lambda _n: 'dealer' in _n.lower() or '自營' in _n)\n"),
        ("                    for _cat, _net in zip(_fm_cats, _df_i['_net']):\n                        if _cat == '外資':\n",
         "                    for _nm, _net in zip(_df_i['name'].astype(str), _df_i['_net']):\n                        _nl = _nm.lower()\n                        if 'foreign' in _nl or '外資' in _nm:\n"),
        ("                        elif _cat == '投信':\n",
         "                        elif 'investment_trust' in _nl or '投信' in _nm:\n"),
        ("                        elif _cat == '自營':\n",
         "                        elif 'dealer' in _nl or '自營' in _nm:\n"),
    ),
    _NAS: (
        ('from shared.inst_labels import is_foreign_dealer_label  # 批 Z40 法人身分別判定 SSOT(L0)\n',
         ''),
        ('                # 批 Z40（客戶 Q-z24＝A\' 官方口徑／Q-z25＝A）：自營商 ＝ 自行＋避險（只加不含「外資」的自營商列）；\n                #   「外資自營商」列已含在自營商內 ⇒ 不加進自營商、也不當外資退路（修前兩處都會撿到它；\n                #   且修前 dealer 條件「含自營商」連「外資及陸資(不含外資自營商)」外資列都會加進來）。\n                _fd_rows = [k for k in raw if is_foreign_dealer_label(k)]\n                if _fd_rows:\n                    print(f"[NAS/institutional] {ds} 略過外資自營商列 {_fd_rows}（官方口徑：已含在自營商內，不另計）")\n                dealer = sum(v for k, v in raw.items() if "自營商" in k and "外資" not in k)\n',
         '                dealer = sum(v for k, v in raw.items() if "自營商" in k)\n'),
        ('                    foreign = next((v for k, v in raw.items()\n                                    if "外資" in k and not is_foreign_dealer_label(k)), 0)\n',
         '                    foreign = next((v for k, v in raw.items() if "外資" in k), 0)\n'),
    ),
    _FFF: (
        ('from shared.inst_labels import is_finmind_foreign_investor, is_foreign_dealer_label  # 批 Z40 SSOT(L0)\n',
         ''),
        ('    # 過濾「外資」類別。批 Z40（客戶 Q-z24＝A\' 官方口徑）：外資 ＝ 只取 name == "Foreign_Investor"\n    #   （＝外資及陸資，不含外資自營商）；中文退路：含「外資」且**非**外資自營商列\n    #   （⚠️ 不能單純排除含「自營」——「外資及陸資(不含外資自營商)」本身就含「自營」）。\n    #   修前 `contains("Foreign|外資")` 會把 Foreign_Dealer_Self 一起加進外資。\n',
         '    # 過濾「外資」類別(含 Foreign_Investor / 外資及陸資 等變體)\n'),
        ('    _names = df[name_col].astype(str)\n    mask = (_names.map(is_finmind_foreign_investor)\n            | (_names.str.contains("外資", na=False, regex=False)\n               & ~_names.map(is_foreign_dealer_label)))\n',
         '    mask = df[name_col].astype(str).str.contains("Foreign|外資", case=False, na=False, regex=True)\n'),
        ("            'FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign_Investor(via leading_indicators.finmind_get)')\n",
         "            'FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign(via leading_indicators.finmind_get)')\n"),
        ("             'FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign_Investor',\n",
         "             'FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign',\n"),
    ),
    _UMH: (
        ('                                             Foreign_Investor；批 Z40 起不含 Foreign_Dealer_Self（外資自營商）；\n                                             投信、自營商不取；歷史列口徑見 `fetch_finmind_inst` docstring）\n',
         '                                             Foreign_Investor ＋ Foreign_Dealer_Self；投信、自營商不取）\n'),
        ('    只取 name == "Foreign_Investor" 的列（＝ 外資及陸資，不含外資自營商），每列 buy − sell，\n',
         "    篩含 'Foreign' 的列（外資總額 = Foreign_Investor ＋ Foreign_Dealer_Self），每列 buy − sell，\n"),
        ('\n    批 Z40（客戶 Q-z24＝A\' 官方口徑，2026-10-11）口徑標註 —— **20 年歷史不重抓，只做標註**：\n    - 官方口徑：外資 ＝ 外資及陸資（不含外資自營商）；外資自營商已含在自營商（自行＋避險）內，\n      不另加到任何一類（TWSE BFI82U notes）。\n    - `data_cache/finmind_inst.parquet` 既有列的口徑（派工規格所載實測事實，本批未重抓驗證）：\n      · 2017-12-18 前：FinMind 來源端 Foreign_Investor 本身含外資自營商；\n      · 2017-12-18 起至本批上線日：本檔以 `contains("Foreign")` 存 Foreign_Investor ＋ Foreign_Dealer_Self\n        加總（仍含外資自營商）；\n      · 本批上線日起：只取 Foreign_Investor（不含外資自營商）。\n      外資自營商 2024 年起實測約 0（同上出處），故近年兩種口徑數值差異極小，但 2017-12-18 ~ 2023 年\n      個別日可能非零（例：BFI82U 2018-03-15 外資自營商差額 -35,206,790 元）。\n    - 列級 metadata：本批起寫出的列 `source` ＝ `FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign_Investor`；\n      本批之前寫出的列為 `...:Foreign`（或更早無 source 欄 → NaN）。增量更新只抓「最後一日之後」\n      （`update_one`：start ＝ last ＋ 1 日；`_merge_dedupe` 依 date 去重），既有列不會被覆寫\n      ⇒ **讀 `source` 欄即可分辨該列是新口徑還是舊口徑**。⚠️ 例外：`--bootstrap`（整段重抓）會以\n      本批口徑重寫全部列（屆時 2017-12-18 前的列仍是 FinMind 來源端含外資自營商的 Foreign_Investor）。\n',
         ''),
        ('    from shared.inst_labels import is_finmind_foreign_investor   # 批 Z40 SSOT(L0)\n',
         ''),
        ('    # 批 Z40（官方口徑）：外資 = 只取 Foreign_Investor；Foreign_Dealer_Self（外資自營商）不計入\n    #   （修前 `contains("Foreign")` 會把它加進外資）。\n',
         "    # 外資總額 = Foreign_Investor + Foreign_Dealer_Self（兩者皆 'Foreign' prefix）\n"),
        ('    fi = raw[raw["name"].astype(str).map(is_finmind_foreign_investor)]\n',
         '    fi = raw[raw["name"].astype(str).str.contains("Foreign", na=False)]\n'),
        ('        # 批 Z40：source 改記 `:Foreign_Investor` ＝ 列級口徑標記（舊列為 `:Foreign`，見 docstring）\n        out["source"] = "FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign_Investor"\n',
         '        out["source"] = "FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign"\n'),
    ),
    _DLIF: (
        ('from shared.inst_labels import (  # 批 Z40 法人身分別判定 SSOT(L0)\n    T86_DEALER_HEDGE_NET_COL, T86_DEALER_NET_COL, T86_DEALER_SELF_NET_COL,\n    T86_FOREIGN_NET_COL, T86_FOREIGN_NET_COL_LEGACY, T86_TOTAL_NET_COL, T86_TRUST_NET_COL,\n    is_foreign_dealer_label)\n',
         ''),
        ('    回傳 {股票代碼: {\'外資\':float, \'投信\':float, \'自營商\':float}}，單位：張\n    批 Z40 官方口徑：外資不含外資自營商、自營商＝自行＋避險；缺欄／髒值／守衛不過 → 該格 NaN（不補 0）。"""\n',
         '    回傳 {股票代碼: {\'外資\':float, \'投信\':float, \'自營商\':float}}，單位：張"""\n'),
        ("        fields = [str(f) for f in j.get('fields', [])]\n",
         "        fields = [str(f) for f in j.get('fields', [])]\n        fi = {n: i for i, n in enumerate(fields)}\n"),
        ("        # 批 Z40（客戶 Q-z24＝A' 官方口徑／Q-z25＝A）：欄名一律 strip 後**完全相等**比對（⛔ 子字串\n        #   `next()` —— 「外資自營商買賣超股數」含「自營商買賣超股數」、「外陸資…(不含外資自營商)」含「自營」）：\n        #   外資 ＝ `外陸資買賣超股數(不含外資自營商)`（2017-12-18 前舊格式備援 `外資買賣超股數`，當時官方口徑）；\n        #   投信 ＝ `投信買賣超股數`；自營商 ＝ `自營商買賣超股數`（idx 11，＝自行＋避險；修前只取「自行買賣」子欄）。\n        #   外資自營商欄不取（已含在自營商內）。任一類找不到欄 → 該類 NaN（Z38 只對外資，本批擴及投信／自營商）。\n        fi = {n.strip(): i for i, n in enumerate(fields)}\n        f_idx = fi.get(T86_FOREIGN_NET_COL)\n",
         "        # 改先挑「含外陸資且含買賣超」(現行格式只命中此欄,與 BFI82U 外資口徑同:外資及陸資、\n        # 不含外資自營商);舊格式「外資買賣超股數」保留原判斷作備援,「外資自營商買賣超股數」\n        # 兩條件皆不命中。\n        f_idx = next((v for k, v in fi.items() if '外陸資' in k and '買賣超' in k), None)\n"),
        ("            f_idx = fi.get(T86_FOREIGN_NET_COL_LEGACY)\n        t_idx = fi.get(T86_TRUST_NET_COL)\n        d_idx = fi.get(T86_DEALER_NET_COL)\n        dself_idx = fi.get(T86_DEALER_SELF_NET_COL)\n        dhedge_idx = fi.get(T86_DEALER_HEDGE_NET_COL)\n        tot_idx = fi.get(T86_TOTAL_NET_COL)\n        print(f'[T86] {ds} fields={fields[:5]} f_idx={f_idx} t_idx={t_idx} d_idx={d_idx} '\n              f'd_self_idx={dself_idx} d_hedge_idx={dhedge_idx} total_idx={tot_idx}')\n",
         "            f_idx = next((v for k, v in fi.items() if '外' in k and '買賣超' in k and '自營' not in k), None)\n        t_idx = next((v for k, v in fi.items() if '投信' in k and '買賣超' in k), None)\n        d_idx = next((v for k, v in fi.items() if '自營' in k and '買賣超' in k and '自行' in k), None)\n        print(f'[T86] {ds} fields={fields[:5]} f_idx={f_idx} t_idx={t_idx} d_idx={d_idx}')\n"),
        ('        def _iv(row, idx):\n            """儲存格 → 股數 int。欄不存在／列太短／空白／\'--\'／非數字 → None（缺值）。\n            批 Z40：修前 `_pn` 對髒儲存格回 0.0（假 0），改回缺值；真 0（\'0\'）仍是 0。"""\n            if idx is None or idx >= len(row): return None\n            try: return int(str(row[idx]).replace(\',\', \'\').replace(\'+\', \'\').strip())\n            except (ValueError, TypeError): return None\n\n        def _lots(v):\n            return float(\'nan\') if v is None else round(v / 1000, 1)   # 股 → 張（單位不變）\n',
         "        def _pn(row, idx):\n            if idx is None or idx >= len(row): return 0.0\n            try: return round(int(str(row[idx]).replace(',', '').replace('+', '') or 0) / 1000, 1)\n            # v19.82:裸 except 收窄(§3.3);髒儲存格 → 0.0 為既有 fail-token 語意\n            except (ValueError, TypeError): return 0.0\n"),
        ('        _n_d_mismatch = _n_d_unverified = _n_tot_mismatch = 0\n',
         ''),
        ("                _f, _t, _d = _iv(row, f_idx), _iv(row, t_idx), _iv(row, d_idx)\n                # 批 Z40 守衛：自行、避險兩子欄都在 ⇒ 逐列驗 自行＋避險 == 自營商；不成立／子欄值不可解析\n                #   ⇒ 該列自營商 NaN（不 raise 整日，避免單列髒資料毀整日）。缺合計欄但兩子欄都在 ⇒ 兩者相加；\n                #   任一子欄缺 ⇒ NaN（⛔ 不得半套）。\n                if dself_idx is not None and dhedge_idx is not None:\n                    _ds_v, _dh_v = _iv(row, dself_idx), _iv(row, dhedge_idx)\n                    if d_idx is None:\n                        _d = None if (_ds_v is None or _dh_v is None) else _ds_v + _dh_v\n                    elif _d is not None and (_ds_v is None or _dh_v is None):\n                        _n_d_unverified += 1\n                        _d = None\n                    elif _d is not None and _ds_v + _dh_v != _d:\n                        _n_d_mismatch += 1\n                        _d = None\n                # log 層級對帳：外資＋投信＋自營商 == 三大法人買賣超股數（不成立只計數）\n                _tot = _iv(row, tot_idx)\n                if None not in (_f, _t, _d, _tot) and _f + _t + _d != _tot:\n                    _n_tot_mismatch += 1\n                day_data[code] = {'外資': _lots(_f), '投信': _lots(_t), '自營商': _lots(_d)}\n        if _n_d_mismatch or _n_d_unverified:\n            print(f'[TWSE T86] ⚠️ {ds} 自營商守衛：自行＋避險≠自營商 {_n_d_mismatch} 列、'\n                  f'子欄不可解析 {_n_d_unverified} 列 → 該列自營商為缺值(NaN)')\n        if _n_tot_mismatch:\n            print(f'[TWSE T86] ⚠️ {ds} 對帳：外資＋投信＋自營商≠三大法人買賣超股數 {_n_tot_mismatch} 列（僅記錄）')\n",
         "                # 批 Z38:找不到外資欄 → NaN(缺值),不回 _pn 的 0.0 假零;交下游既有缺值路徑\n                day_data[code] = {'外資': _pn(row, f_idx) if f_idx is not None else float('nan'),\n                                  '投信': _pn(row, t_idx), '自營商': _pn(row, d_idx)}\n"),
        ("    # 批 Z40（客戶 Q-z24＝A' 官方口徑／Q-z25＝A）：外資自營商（Foreign_Dealer_Self／「外資自營商…」欄）\n    #   已含在自營商（自行＋避險）內 ⇒ 在 rename 之前明確 drop，不計入任何一類。\n    #   （修前註解「外資自營商屬外資陣營，應歸入外資」→ 英文 Foreign_Dealer_Self 被 'foreign' 歸外資；\n    #   若只改外資條件，它會掉進下方 'dealer' in cl 被加進自營商 —— 兩者都是重複計算。）\n    _fd_cols = [c for c in pv.columns if c != 'date' and is_foreign_dealer_label(c)]\n    if _fd_cols:\n        print(f'[INST-RENAME] 略過外資自營商欄 {_fd_cols}（官方口徑：已含在自營商自行＋避險內，不另計）')\n        pv = pv.drop(columns=_fd_cols)\n",
         ''),
        ('    # 重命名：支援英文（Foreign_Investor）與中文（外陸資…）\n',
         '    # 重命名：支援英文（Foreign_Investor）與中文（外陸資…）\n    # 注意：外資自營商 屬外資陣營，應歸入「外資」而非「自營商」\n'),
        ("            rn[c] = '外資'          # 外陸資(不含外資自營商)；外資自營商已於上方 drop（批 Z40）\n",
         "            rn[c] = '外資'          # 外陸資(不含外資自營商) + 外資自營商 → 均歸外資\n"),
        ("            rn[c] = '外資'          # 英文名稱（Foreign_Investor；Foreign_Dealer_Self 已於上方 drop，批 Z40）\n",
         "            rn[c] = '外資'          # 英文名稱（含 dealer）\n"),
        ("            rn[c] = '自營商'        # Dealer_self ＋ Dealer_Hedging（自行＋避險，下方重複欄合併加總）\n",
         "            rn[c] = '自營商'\n"),
    ),
    _MCR: (
        ("    # 批 Z40（客戶 Q-z24＝A'）口徑標註：finmind_inst.parquet 的 foreign_buy 口徑隨寫入時點而異 ——\n    #   2017-12-18 前 FinMind Foreign_Investor 本身含外資自營商；2017-12-18 起至 Z40 上線日存 Foreign_Investor\n    #   ＋ Foreign_Dealer_Self（含外資自營商）；Z40 上線日起只取 Foreign_Investor（不含）。歷史不重抓；\n    #   列級 `source` 欄可分辨（`...:Foreign` 舊／`...:Foreign_Investor` 新），詳\n    #   scripts/update_macro_history.py::fetch_finmind_inst。外資自營商 2024 年起實測約 0（派工規格轉述）。\n",
         ''),
    ),
    _EXP: (
        ('    - `institutional_flow`  外資買賣超（finmind_inst.parquet,單位 億元；批 Z40 口徑標註：\n                            2017-12-18 前含外資自營商(FinMind 來源端)、2017-12-18 起至 Z40 上線日\n                            存 Foreign_Investor＋Foreign_Dealer_Self(含)、Z40 上線日起只取\n                            Foreign_Investor(不含外資自營商)；歷史不重抓,見 write_institutional_flow）\n',
         '    - `institutional_flow`  外資買賣超（finmind_inst.parquet,單位 億元）\n'),
        ("    # 批 Z40（客戶 Q-z24＝A'）口徑標註：parquet 既有列口徑隨寫入時點而異（見\n    #   scripts/update_macro_history.py::fetch_finmind_inst docstring）—— 2017-12-18 前 FinMind\n    #   Foreign_Investor 本身含外資自營商；2017-12-18 起至 Z40 上線日存 FI＋FDS 加總（含外資自營商）；\n    #   Z40 上線日起只取 Foreign_Investor（不含）。歷史不重抓；外資自營商 2024 年起實測約 0。\n    #   本表不帶 source 欄（schema 不變）；需分辨口徑時讀 parquet 的列級 source。\n",
         ''),
    ),
}
#: 基底 `ba470b9b` 原始檔 sha256（`git show ba470b9b:<檔> | sha256sum` 實算；寫死以免測試依賴 git）
Z40_BASE_SHA = {
    _DDF: '546fad00f6b0446e038a8b089f9fe796a9abf16d82a51d06f73d77f69d6949b7',
    _ORCH: '7056b7e771b0065558a9497adc25b974b41454479eb4fc615aa9be87459e5951',
    _NAS: 'cb591a9aa1743d30d435768066cabcdb3c31ef17d87e5537c58f256e76565848',
    _FFF: '48258cf67d709575cced09951146c706e47b4a66930ae4cd562318839768dbe1',
    _UMH: '3cbb418f95ebbd8ff12f2a533b2311d116e8e8bcbf00776e185f5a6e342162fc',
    _DLIF: '84527a7f275c311c4060084c1925b8d0b71966eb1f9b0d818ec09d786d87ddc8',
    _MCR: '059accd6cd3783530a1df29c62d527827dbe2128820445743175e56e51332fe2',
    _EXP: '096c1887b6154dbc8a973e91fb07ef76dc3a1eb5460007aad17a7200873fddcb',
}


def z40_revert_for(file_path, code: str) -> str:
    """舊批次還原鏈串接用：給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣）。"""
    p = pathlib.Path(file_path)
    rel = (p.resolve().relative_to(_ROOT) if p.is_absolute() else p).as_posix()
    for new, old in Z40_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f'{rel} 替換點不唯一或已不存在：{new!r}'
        code = code.replace(new, old)
    return code


def _exec_module(rel: str, code: str, name: str):
    path = _ROOT / rel
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(path)
    sys.modules[name] = m          # dataclass 等需要以模組名回查
    exec(compile(code, str(path), 'exec'), m.__dict__)
    return m


@functools.lru_cache(maxsize=None)
def z40_pre_module(rel: str):
    """現行檔只把本批改動換回基底 `ba470b9b` 寫法（獨立模組物件，不影響本尊）。"""
    code = z40_revert_for(rel, (_ROOT / rel).read_text(encoding='utf-8'))
    return _exec_module(rel, code, '_z40_pre_' + rel.replace('/', '_').removesuffix('.py'))


def _mutant_module(rel: str, swaps, tag: str):
    """單點突變：現行檔做指定替換（每組恰一處）後載入成獨立模組。"""
    code = (_ROOT / rel).read_text(encoding='utf-8')
    for new, old in swaps:
        assert code.count(new) == 1, f'突變點不唯一或已不存在：{new!r}'
        code = code.replace(new, old)
    return _exec_module(rel, code, f'_z40_mut_{tag}')


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案與舊批次測試
# ══════════════════════════════════════════════════════════════════════════
import datetime as _dt  # noqa: E402
import math  # noqa: E402

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

import scripts.update_macro_history as UMH  # noqa: E402
import src.data.core.data_loader_inst_fetchers as IFX  # noqa: E402
import src.data.macro.foreign_flow_fetcher as FFF  # noqa: E402
from shared import inst_labels as L  # noqa: E402
from src.data.daily.daily_data_fetchers import _parse_bfi82u_rows  # noqa: E402
from tests import test_lamp_foreign_net_wiring as LAMP  # noqa: E402


@pytest.mark.parametrize('rel', sorted(Z40_REVERT_PAIRS))
def test_reverted_source_equals_base_file(rel):
    """還原體原始碼逐字 ＝ 基底 `ba470b9b` 檔案 ⇒ 下方「修前」對照與突變斷言都是真修前碼。"""
    code = z40_revert_for(rel, (_ROOT / rel).read_text(encoding='utf-8'))
    assert hashlib.sha256(code.encode('utf-8')).hexdigest() == Z40_BASE_SHA[rel]


def test_z36_chain_includes_z40_pairs():
    """Z36 還原鏈已串接本批（否則 Z36 的 `test_reverted_source_equals_base_file` 會對 DDF／ORCH 轉紅）。"""
    from tests import test_batch_z36 as Z36
    for rel in (_DDF, _ORCH):
        code = Z36.z36_revert(rel, (_ROOT / rel).read_text(encoding='utf-8'))
        assert hashlib.sha256(code.encode('utf-8')).hexdigest() == Z36.Z36_BASE_SHA[rel]


# ══════════════════════════════════════════════════════════════════════════
# L0 判定 SSOT
# ══════════════════════════════════════════════════════════════════════════
class TestInstLabels:
    @pytest.mark.parametrize('name', ['外資自營商', '外資自營商買賣超股數', ' 外資自營商 ',
                                      'Foreign_Dealer_Self', 'foreign_dealer_self', ' Foreign_Dealer_Self '])
    def test_foreign_dealer_true(self, name):
        assert L.is_foreign_dealer_label(name)

    @pytest.mark.parametrize('name', ['外資及陸資(不含外資自營商)', '外陸資買賣超股數(不含外資自營商)',
                                      '外資及陸資', '自營商(自行買賣)', '自營商(避險)', '自營商買賣超股數',
                                      '投信', 'Foreign_Investor', 'Dealer_self', 'Dealer_Hedging', 'total', ''])
    def test_foreign_dealer_false(self, name):
        assert not L.is_foreign_dealer_label(name)

    def test_finmind_exact(self):
        assert L.is_finmind_foreign_investor('Foreign_Investor')
        assert not L.is_finmind_foreign_investor('Foreign_Dealer_Self')
        assert L.is_finmind_dealer('Dealer_self') and L.is_finmind_dealer('Dealer_Hedging')
        assert not L.is_finmind_dealer('Foreign_Dealer_Self')

    def test_t86_column_constants_are_official_names(self):
        assert L.T86_FOREIGN_NET_COL == '外陸資買賣超股數(不含外資自營商)'
        assert L.T86_TRUST_NET_COL == '投信買賣超股數'
        assert L.T86_DEALER_NET_COL == '自營商買賣超股數'
        assert L.T86_DEALER_SELF_NET_COL == '自營商買賣超股數(自行買賣)'
        assert L.T86_DEALER_HEDGE_NET_COL == '自營商買賣超股數(避險)'
        assert L.T86_TOTAL_NET_COL == '三大法人買賣超股數'
        # 子字串陷阱（模組存在的理由）
        assert L.T86_DEALER_NET_COL in '外資自營商買賣超股數'


# ══════════════════════════════════════════════════════════════════════════
# 1. BFI82U 解析器（市場總額；外資自營商不再重複計入自營商）
# ══════════════════════════════════════════════════════════════════════════
_BFI_FIELDS = ['單位名稱', '買進金額', '賣出金額', '買賣差額']


def _bfi_rows(fd='200,000,000', *, foreign='15,000,000,000', trust='1,230,000,000',
              dself='1,000,000,000', dhedge='-550,000,000', with_dom_dealer=True):
    """BFI82U 官方 6 列（列名＝官方實測）；fd=None ⇒ 無外資自營商列。合計 ＝ 自行＋避險＋投信＋外資(不含)。"""
    rows = []
    if with_dom_dealer:
        rows += [['自營商(自行買賣)', '1', '1', dself], ['自營商(避險)', '1', '1', dhedge]]
    rows.append(['投信', '1', '1', trust])
    rows.append(['外資及陸資(不含外資自營商)', '1', '1', foreign])
    if fd is not None:
        rows.append(['外資自營商', '1', '1', fd])
    rows.append(['合計', '1', '1', '0'])
    return rows


def _bfi(parser=None, **kw):
    return (parser or _parse_bfi82u_rows)(_BFI_FIELDS, _bfi_rows(**kw))


class TestBfi82u:
    def test_foreign_dealer_not_added_to_dealer(self, capsys):
        inst = _bfi()                                          # 外資自營商 +2.0 億
        assert inst['自營商']['net'] == 4.5                    # 10.0 + (-5.5)，不含外資自營商
        assert inst['外資及陸資']['net'] == 150.0              # 也不歸外資
        assert inst['投信']['net'] == 12.3
        assert inst.unobserved_net == frozenset()
        out = capsys.readouterr().out
        assert '略過「外資自營商」列 2.0 億' in out

    def test_negative_foreign_dealer_not_added(self):
        assert _bfi(fd='-35,206,790')['自營商']['net'] == 4.5   # 歷史日（2018-03-15 級）非零

    def test_same_as_no_foreign_dealer_row(self):
        assert repr(_bfi()) == repr(_bfi(fd=None))
        assert _bfi().unobserved_net == _bfi(fd=None).unobserved_net

    def test_only_foreign_dealer_is_unobserved_not_counted(self):
        inst = _bfi(with_dom_dealer=False)
        assert inst.unobserved_net == frozenset({'自營商'})   # Z36 旗標語意不變
        assert inst['自營商']['net'] == 0.0                   # 預填（既有），⛔ 不是外資自營商的 2.0

    def test_foreign_dealer_dashdash_ignored(self):
        assert repr(_bfi(fd='--')) == repr(_bfi(fd=None))

    def test_pre_fix_double_counted(self):
        """突變（整檔還原）：修前把外資自營商加進自營商 ⇒ 6.5 ⇒ 上方斷言轉紅。"""
        pre = z40_pre_module(_DDF)._parse_bfi82u_rows
        assert _bfi(parser=pre)['自營商']['net'] == 6.5
        assert _bfi(parser=pre, with_dom_dealer=False)['自營商']['net'] == 2.0

    def test_mutant_remove_fd_branch(self):
        """單點突變：拔掉 `elif is_foreign_dealer_label(_nm):` 分支 ⇒ 外資自營商落進「自營」⇒ 6.5。"""
        m = _mutant_module(_DDF, [("        elif is_foreign_dealer_label(_nm):\n", "        elif False:\n")],
                           'ddf_fd')
        assert _bfi(parser=m._parse_bfi82u_rows)['自營商']['net'] == 6.5


#: tests/test_batch_z36.py 的 `_QZ20_GOLDEN[(ek, 'foreign_dealer_parsed')]` 在 Z40 前的值（自營商 6.5 雙計口徑）
_Z36_OLD_FD_PARSED_GOLDEN = {
    'chips': 'eb1564fee86240aa4c0984b645189b53ec75ca3f59350237b9cca3ae62222cc0',
    'news': '257b3837464adc0c162898eba18aeee08fce4ec1262cd084e6be31c66273ab3e',
}


@pytest.mark.parametrize('ek', sorted(_Z36_OLD_FD_PARSED_GOLDEN))
def test_z36_foreign_dealer_parsed_old_golden_is_double_count(ek, monkeypatch):
    """Z36 golden 更新的佐證：舊 golden ＝ Z40 前解析器（外資自營商併入自營商 6.5）餵進同一批消費點的輸出；
    新解析器輸出 ＝ normal_pos 的 golden（外資自營商不計入）。"""
    from tests import test_batch_z36 as Z36
    now = Z36.OBSERVED['foreign_dealer_parsed']()
    assert Z36._digest(ek, Z36._RUN[ek](Z36._mod(ek), now, monkeypatch)) == Z36._QZ20_GOLDEN[(ek, 'normal_pos')]
    monkeypatch.setattr(Z36, '_parse_bfi82u_rows', z40_pre_module(_DDF)._parse_bfi82u_rows)
    old = Z36.OBSERVED['foreign_dealer_parsed']()
    assert old['自營商']['net'] == 6.5
    assert Z36._digest(ek, Z36._RUN[ek](Z36._mod(ek), old, monkeypatch)) == _Z36_OLD_FD_PARSED_GOLDEN[ek]


# ══════════════════════════════════════════════════════════════════════════
# 2. FinMind 補救（macro_fetch_orchestrator）
# ══════════════════════════════════════════════════════════════════════════
_fm = LAMP._fm_row
_FM_EN = [_fm('Foreign_Investor', 30_000_000_000, 55_000_000_000),      # -250.0
          _fm('Foreign_Dealer_Self', 900_000_000, 100_000_000),         # +8.0（不得計入任何一類）
          _fm('Investment_Trust', 5_000_000_000, 3_000_000_000),        # +20.0
          _fm('Dealer_self', 1_000_000_000, 2_000_000_000),             # -10.0
          _fm('Dealer_Hedging', 4_000_000_000, 1_000_000_000),          # +30.0
          _fm('total', 40_900_000_000, 61_100_000_000)]
_FM_ZH = [_fm('外資及陸資(不含外資自營商)', 30_000_000_000, 55_000_000_000),
          _fm('外資自營商', 900_000_000, 100_000_000),
          _fm('投信', 5_000_000_000, 3_000_000_000),
          _fm('自營商(自行買賣)', 1_000_000_000, 2_000_000_000),
          _fm('自營商(避險)', 4_000_000_000, 1_000_000_000)]


def _fm_inst(mp, rows, orch=None):
    if orch is not None:
        mp.setattr('src.services.macro_fetch_orchestrator.fetch_macro_bundle', orch.fetch_macro_bundle)
    return LAMP._finmind_bundle(mp, rows)['inst']


class TestFinMindRescue:
    @pytest.mark.parametrize('rows', [_FM_EN, _FM_ZH], ids=['en', 'zh'])
    def test_official_caliber(self, rows, monkeypatch, capsys):
        inst = _fm_inst(monkeypatch, rows)
        assert inst['外資及陸資']['net'] == -250.0      # 只取 Foreign_Investor
        assert inst['投信']['net'] == 20.0
        assert inst['自營商']['net'] == 20.0            # 自行 -10 ＋ 避險 +30；外資自營商 +8 不計
        assert set(inst) == {'外資及陸資', '投信', '自營商'}
        assert inst.unobserved_net == frozenset()
        assert '略過外資自營商 1 列' in capsys.readouterr().out

    def test_foreign_dealer_bad_value_flags_nothing(self, monkeypatch):
        rows = [r if r['name'] != 'Foreign_Dealer_Self' else _fm('Foreign_Dealer_Self', None, 1)
                for r in _FM_EN]
        inst = _fm_inst(monkeypatch, rows)
        assert inst.unobserved_net == frozenset()       # 外資自營商不屬任何一類 ⇒ 其缺值不標任何類
        assert inst['外資及陸資']['net'] == -250.0

    def test_only_foreign_dealer_gives_no_dealer_key(self, monkeypatch):
        inst = _fm_inst(monkeypatch, [_FM_EN[0], _FM_EN[1], _FM_EN[2]])
        assert '自營商' not in inst and inst['外資及陸資']['net'] == -250.0

    def test_pre_fix_foreign_included_foreign_dealer(self, monkeypatch):
        """突變（整檔還原）：修前 'foreign' 子字串把 Foreign_Dealer_Self 歸外資 ⇒ -242.0 ⇒ 上方斷言轉紅。"""
        inst = _fm_inst(monkeypatch, _FM_EN, orch=z40_pre_module(_ORCH))
        assert inst['外資及陸資']['net'] == -242.0
        inst_zh = _fm_inst(monkeypatch, _FM_ZH, orch=z40_pre_module(_ORCH))
        assert inst_zh['外資及陸資']['net'] == -242.0

    def test_mutant_foreign_substring(self, monkeypatch):
        """單點突變：拔掉外資自營商守衛並把外資判定改回 'foreign' 子字串 ⇒ Foreign_Dealer_Self 歸外資 ⇒ -242.0。"""
        m = _mutant_module(_ORCH, [
            ("                        if is_foreign_dealer_label(_n):\n                            return None\n", ''),
            ("                        if is_finmind_foreign_investor(_n) or '外資' in _n:\n",
             "                        if 'foreign' in _n.lower() or '外資' in _n:\n")], 'orch_fd')
        assert _fm_inst(monkeypatch, _FM_EN, orch=m)['外資及陸資']['net'] == -242.0

    def test_mutant_dealer_substring(self, monkeypatch):
        """單點突變：拔 FD 守衛、自營改回 'dealer' 子字串、外資只認 Foreign_Investor ⇒ 外資自營商掉進自營商。"""
        m = _mutant_module(_ORCH, [
            ("                        if is_foreign_dealer_label(_n):\n                            return None\n", ''),
            ("                        if is_finmind_dealer(_n) or ('自營' in _n and '外資' not in _n):\n",
             "                        if 'dealer' in _n.lower() or '自營' in _n:\n")], 'orch_dealer')
        assert _fm_inst(monkeypatch, _FM_EN, orch=m)['自營商']['net'] == 28.0


# ══════════════════════════════════════════════════════════════════════════
# 3. NAS 中繼站 BFI82U（以 stub fastapi／pydantic 載入，沙箱未裝 fastapi）
# ══════════════════════════════════════════════════════════════════════════
def _stub_web(mp):
    fa = types.ModuleType('fastapi')

    class _App:
        def __init__(self, *a, **k):
            pass

        def __getattr__(self, _n):
            return lambda *a, **k: (lambda f: f)
    fa.FastAPI = _App
    fa.HTTPException = type('HTTPException', (Exception,), {'__init__': lambda self, *a, **k: None})
    fa.Depends = lambda *a, **k: None
    fa.Header = lambda *a, **k: None
    far = types.ModuleType('fastapi.responses')
    far.Response = object
    pd_ = types.ModuleType('pydantic')
    pd_.BaseModel = object
    mp.setitem(sys.modules, 'fastapi', fa)
    mp.setitem(sys.modules, 'fastapi.responses', far)
    mp.setitem(sys.modules, 'pydantic', pd_)


def _nas_module(mp, *, pre=False):
    _stub_web(mp)
    code = (_ROOT / _NAS).read_text(encoding='utf-8')
    if pre:
        code = z40_revert_for(_NAS, code)
    return _exec_module(_NAS, code, '_z40_nas_pre' if pre else '_z40_nas_now')


def _nas_fetch(mp, mod, rows):
    payload = {'stat': 'OK', 'fields': _BFI_FIELDS, 'data': rows}

    class _R:
        def json(self):
            return payload
    mp.setattr(mod, 'requests', types.SimpleNamespace(get=lambda *a, **k: _R()))
    return mod._fetch_institutional('20261008')


class TestNasServer:
    def test_official_caliber(self, monkeypatch):
        out = _nas_fetch(monkeypatch, _nas_module(monkeypatch), _bfi_rows())
        assert out == {'外資及陸資': {'net': 150.0}, '投信': {'net': 12.3}, '自營商': {'net': 4.5}}

    def test_foreign_fallback_skips_foreign_dealer(self, monkeypatch):
        """外資及陸資列缺 ⇒ 退路不得撿到外資自營商列（放在前面）。"""
        rows = [['外資自營商', '1', '1', '200,000,000'], ['外資', '1', '1', '7,000,000,000'],
                ['投信', '1', '1', '1,230,000,000'], ['自營商(自行買賣)', '1', '1', '1,000,000,000'],
                ['自營商(避險)', '1', '1', '-550,000,000']]
        out = _nas_fetch(monkeypatch, _nas_module(monkeypatch), rows)
        assert out['外資及陸資']['net'] == 70.0 and out['自營商']['net'] == 4.5

    def test_pre_fix_double_counted(self, monkeypatch):
        """突變（整檔還原）：修前自營商 ＝「含自營商」全加 ⇒ 連外資及陸資(不含外資自營商)列與外資自營商列都加進來。"""
        pre = _nas_fetch(monkeypatch, _nas_module(monkeypatch, pre=True), _bfi_rows())
        assert pre['自營商']['net'] == round(4.5 + 2.0 + 150.0, 2)
        rows = [['外資自營商', '1', '1', '200,000,000'], ['外資', '1', '1', '7,000,000,000'],
                ['投信', '1', '1', '1,230,000,000']]
        pre2 = _nas_fetch(monkeypatch, _nas_module(monkeypatch, pre=True), rows)
        assert pre2['外資及陸資']['net'] == 2.0                  # 修前退路撿到外資自營商


# ══════════════════════════════════════════════════════════════════════════
# 4. 外資資金流量序列（foreign_flow_fetcher）
# ══════════════════════════════════════════════════════════════════════════
def _flow_df(names_vals, date='2026-10-08'):
    return pd.DataFrame([{'date': date, 'name': n, 'buy': b, 'sell': s} for n, b, s in names_vals])


_FLOW_EN = [('Foreign_Investor', 30_000_000_000, 55_000_000_000), ('Foreign_Dealer_Self', 900_000_000, 100_000_000),
            ('Investment_Trust', 5_000_000_000, 3_000_000_000), ('Dealer_self', 1, 2), ('total', 1, 1)]
_FLOW_ZH = [('外資及陸資(不含外資自營商)', 30_000_000_000, 55_000_000_000), ('外資自營商', 900_000_000, 100_000_000),
            ('投信', 5_000_000_000, 3_000_000_000)]


def _flow(mp, mod, rows, days):
    import src.data.macro as _pkg
    mp.setattr(_pkg, 'finmind_get', lambda *a, **k: _flow_df(rows), raising=False)
    fn = mod.fetch_foreign_flow_series
    if hasattr(fn, 'clear'):
        fn.clear()
    df, err = fn(days, 'tok')
    assert err == ''
    return float(df['foreign_net_yi'].iloc[0])


class TestForeignFlow:
    @pytest.mark.parametrize('rows', [_FLOW_EN, _FLOW_ZH], ids=['en', 'zh'])
    def test_foreign_investor_only(self, rows, monkeypatch):
        assert _flow(monkeypatch, FFF, rows, 4001) == -250.0

    def test_pre_fix_included_foreign_dealer(self, monkeypatch):
        """突變（整檔還原）：修前 contains("Foreign|外資") ⇒ -242.0 ⇒ 上方斷言轉紅。"""
        assert _flow(monkeypatch, z40_pre_module(_FFF), _FLOW_EN, 4002) == -242.0
        assert _flow(monkeypatch, z40_pre_module(_FFF), _FLOW_ZH, 4003) == -242.0

    def test_mutant_zh_fallback_without_fd_guard(self, monkeypatch):
        """單點突變：中文退路拔掉外資自營商排除 ⇒ 「外資自營商」被加進外資。"""
        m = _mutant_module(_FFF, [("               & ~_names.map(is_foreign_dealer_label)))\n", "))\n")],
                           'fff_zh')
        assert _flow(monkeypatch, m, _FLOW_ZH, 4004) == -242.0


# ══════════════════════════════════════════════════════════════════════════
# 5. update_macro_history.fetch_finmind_inst（只取 Foreign_Investor；歷史只標註）
# ══════════════════════════════════════════════════════════════════════════
_INST_DATES = ('2026-10-06', '2026-10-07', '2026-10-08')


def _umh_raw(fds_buy=900_000_000):
    rows = []
    for i, d in enumerate(_INST_DATES):
        rows += [{'buy': 30_000_000_000 + i, 'date': d, 'name': 'Foreign_Investor', 'sell': 55_000_000_000},
                 {'buy': fds_buy, 'date': d, 'name': 'Foreign_Dealer_Self', 'sell': 100_000_000},
                 {'buy': 5_000_000_000, 'date': d, 'name': 'Investment_Trust', 'sell': 3_000_000_000},
                 {'buy': 1_000_000_000, 'date': d, 'name': 'Dealer_self', 'sell': 2_000_000_000},
                 {'buy': 4_000_000_000, 'date': d, 'name': 'Dealer_Hedging', 'sell': 1_000_000_000}]
    return pd.DataFrame(rows)[['buy', 'date', 'name', 'sell']]


def _umh_run(mp, mod, raw):
    mp.setattr(mod, '_finmind_get', lambda *a, **k: raw.copy())
    return mod.fetch_finmind_inst(_dt.date(2026, 10, 6), _dt.date(2026, 10, 8), 'tok')


class TestUpdateMacroHistoryInst:
    def test_foreign_investor_only(self, monkeypatch):
        got = _umh_run(monkeypatch, UMH, _umh_raw())
        exp = [(30_000_000_000 + i - 55_000_000_000) / 1e8 for i in range(3)]
        assert got['foreign_buy'].tolist() == exp            # 逐位（同一算式），不含外資自營商 +8 億
        assert (got['source'] == 'FinMind:TaiwanStockTotalInstitutionalInvestors:Foreign_Investor').all()

    def test_foreign_dealer_missing_does_not_drop_day(self, monkeypatch, capsys):
        raw = _umh_raw().astype({'buy': object})
        raw.loc[raw['name'] == 'Foreign_Dealer_Self', 'buy'] = None
        got = _umh_run(monkeypatch, UMH, raw)
        assert len(got) == 3 and '剔除' not in capsys.readouterr().out

    def test_only_foreign_dealer_rows_is_empty_with_existing_log(self, monkeypatch, capsys):
        raw = _umh_raw()
        raw = raw[raw['name'] == 'Foreign_Dealer_Self']
        assert _umh_run(monkeypatch, UMH, raw).empty
        assert "name 欄位無 'Foreign' 列" in capsys.readouterr().out    # 既有 log 字串保留

    def test_pre_fix_summed_foreign_dealer(self, monkeypatch):
        """突變（整檔還原）：修前 contains("Foreign") ⇒ 每日多 +8 億、FDS 缺值會整日剔除 ⇒ 上方斷言轉紅。"""
        got = _umh_run(monkeypatch, z40_pre_module(_UMH), _umh_raw())
        assert got['foreign_buy'].tolist() == pytest.approx(
            [(30_000_000_000 + i - 55_000_000_000) / 1e8 + 8.0 for i in range(3)], abs=1e-9)
        raw = _umh_raw().astype({'buy': object})
        raw.loc[raw['name'] == 'Foreign_Dealer_Self', 'buy'] = None
        assert _umh_run(monkeypatch, z40_pre_module(_UMH), raw).empty

    def test_caliber_annotations_present(self):
        """口徑標註（docstring／註解／列級 source）在：2017-12-18 前後與本批上線日三段；不檢查 UI。"""
        doc = UMH.fetch_finmind_inst.__doc__
        for s in ('批 Z40', '2017-12-18 前', '2017-12-18 起至本批上線日', '本批上線日起',
                  'Foreign_Investor', 'Foreign_Dealer_Self', '不含外資自營商', '2024 年起實測約 0',
                  '歷史不重抓'):
            assert s in doc, s
        mod_doc = ' '.join(UMH.__doc__.split())
        assert '批 Z40 起不含 Foreign_Dealer_Self' in mod_doc
        for rel in (_MCR, _EXP):
            src = (_ROOT / rel).read_text(encoding='utf-8')
            assert '批 Z40' in src and '2017-12-18' in src and 'Foreign_Investor' in src, rel


# ══════════════════════════════════════════════════════════════════════════
# 6. 個股 FinMind 法人 pivot（_normalize_inst_pivot，上市櫃共用）
# ══════════════════════════════════════════════════════════════════════════
def _pv_raw(names):
    vals = {'Foreign_Investor': (5000, 1000), 'Foreign_Dealer_Self': (9000, 0), 'Investment_Trust': (100, 300),
            'Dealer_self': (2000, 0), 'Dealer_Hedging': (0, 500),
            '外資及陸資(不含外資自營商)': (5000, 1000), '外資自營商': (9000, 0), '投信': (100, 300),
            '自營商(自行買賣)': (2000, 0), '自營商(避險)': (0, 500)}
    return pd.DataFrame([{'date': '2026-10-08', 'name': n, 'buy': vals[n][0], 'sell': vals[n][1]}
                         for n in names])


_PV_EN = ['Foreign_Investor', 'Foreign_Dealer_Self', 'Investment_Trust', 'Dealer_self', 'Dealer_Hedging']
_PV_ZH = ['外資及陸資(不含外資自營商)', '外資自營商', '投信', '自營商(自行買賣)', '自營商(避險)']


class TestNormalizePivot:
    @pytest.mark.parametrize('names', [_PV_EN, _PV_ZH], ids=['en', 'zh'])
    def test_official_caliber(self, names, capsys):
        pv = IFX._normalize_inst_pivot(_pv_raw(names))
        assert list(pv.columns) == ['date', '外資', '投信', '自營商', '主力合計']
        r = pv.iloc[0]
        assert (r['外資'], r['投信'], r['自營商']) == (4.0, -0.2, 1.5)    # 自營 ＝ 自行 2.0 ＋ 避險 -0.5
        assert r['主力合計'] == pytest.approx(5.3)                     # 不含外資自營商 9.0
        assert '略過外資自營商欄' in capsys.readouterr().out

    def test_pre_fix_foreign_absorbed_foreign_dealer(self):
        """突變（整檔還原）：修前外資自營商歸外資 ⇒ 外資 13.0、主力合計 14.3 ⇒ 上方斷言轉紅。"""
        r = z40_pre_module(_DLIF)._normalize_inst_pivot(_pv_raw(_PV_EN)).iloc[0]
        assert r['外資'] == 13.0 and r['主力合計'] == pytest.approx(14.3)

    def test_mutant_without_drop_foreign_cond_only(self):
        """單點突變：拔掉 drop、只把英文外資條件改成 Foreign_Investor ⇒ Foreign_Dealer_Self 掉進 'dealer' ⇒ 自營 10.5。"""
        m = _mutant_module(_DLIF, [
            ("        pv = pv.drop(columns=_fd_cols)\n", "        pass\n"),
            ("        elif 'foreign' in cl:\n", "        elif cl == 'foreign_investor':\n")], 'pivot')
        r = m._normalize_inst_pivot(_pv_raw(_PV_EN)).iloc[0]
        assert r['自營商'] == 10.5 and r['外資'] == 4.0


# ══════════════════════════════════════════════════════════════════════════
# 7. TWSE T86（_get_t86_day）
# ══════════════════════════════════════════════════════════════════════════
#: 官方 19 欄（runner 探針實測欄名，順序同官方）
FIELDS_NOW = [
    '證券代號', '證券名稱',
    '外陸資買進股數(不含外資自營商)', '外陸資賣出股數(不含外資自營商)', '外陸資買賣超股數(不含外資自營商)',
    '外資自營商買進股數', '外資自營商賣出股數', '外資自營商買賣超股數',
    '投信買進股數', '投信賣出股數', '投信買賣超股數',
    '自營商買賣超股數',
    '自營商買進股數(自行買賣)', '自營商賣出股數(自行買賣)', '自營商買賣超股數(自行買賣)',
    '自營商買進股數(避險)', '自營商賣出股數(避險)', '自營商買賣超股數(避險)',
    '三大法人買賣超股數',
]
#: 故意把「外資自營商買賣超股數」與子欄放在「自營商買賣超股數」前面（子字串 next() 會先撿到錯欄）
FIELDS_FD_FIRST = ['證券代號', '證券名稱', '外資自營商買賣超股數', '自營商買賣超股數(自行買賣)',
                   '自營商買賣超股數(避險)', '自營商買賣超股數', '投信買賣超股數',
                   '外陸資買賣超股數(不含外資自營商)', '三大法人買賣超股數']
FIELDS_OLD = [
    '證券代號', '證券名稱', '外資買進股數', '外資賣出股數', '外資買賣超股數',
    '投信買進股數', '投信賣出股數', '投信買賣超股數', '自營商買賣超股數',
    '自營商買進股數(自行買賣)', '自營商賣出股數(自行買賣)', '自營商買賣超股數(自行買賣)',
    '自營商買進股數(避險)', '自營商賣出股數(避險)', '自營商買賣超股數(避險)', '三大法人買賣超股數',
]


def _vals(foreign=5_000_000, fd=10_000, trust=-200_000, dself=50_000, dhedge=-20_000, dealer=None, total=None):
    dealer = dself + dhedge if dealer is None else dealer
    total = foreign + trust + dealer if total is None else total     # 官方：不含外資自營商
    return {'外陸資買賣超股數(不含外資自營商)': foreign, '外資買賣超股數': foreign, '外資自營商買賣超股數': fd,
            '投信買賣超股數': trust, '自營商買賣超股數': dealer, '自營商買賣超股數(自行買賣)': dself,
            '自營商買賣超股數(避險)': dhedge, '三大法人買賣超股數': total}


def _row(fields, code, vals):
    def _fmt(v):
        return v if isinstance(v, str) else f'{v:,}'
    return [code, '測試'] + [_fmt(vals.get(f, 0)) for f in fields[2:]]


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


def _t86(mp, mod, fields, rows):
    mp.setattr(mod, '_T86_DAY_CACHE', {})
    mp.setattr(mod, '_T86_FAIL_TS', {})
    payload = {'stat': 'OK', 'fields': list(fields), 'data': [list(r) for r in rows]}
    mp.setattr(mod, '_fetch_url_dl', lambda *a, **k: _Resp(payload))
    return mod._get_t86_day('20261008')


def _isnan(x):
    return isinstance(x, float) and math.isnan(x)


class TestT86:
    @pytest.mark.parametrize('fields', [FIELDS_NOW, FIELDS_FD_FIRST], ids=['official', 'fd_first'])
    def test_official_caliber(self, fields, monkeypatch, capsys):
        d = _t86(monkeypatch, IFX, fields, [_row(fields, '2330', _vals())])
        assert d == {'2330': {'外資': 5000.0, '投信': -200.0, '自營商': 30.0}}   # 自營＝自行50＋避險-20
        out = capsys.readouterr().out
        assert '自營商守衛' not in out and '對帳' not in out

    def test_official_log_indices(self, monkeypatch, capsys):
        _t86(monkeypatch, IFX, FIELDS_NOW, [_row(FIELDS_NOW, '2330', _vals())])
        assert 'f_idx=4 t_idx=10 d_idx=11 d_self_idx=14 d_hedge_idx=17 total_idx=18' in capsys.readouterr().out

    def test_old_format(self, monkeypatch):
        d = _t86(monkeypatch, IFX, FIELDS_OLD, [_row(FIELDS_OLD, '2330', _vals(foreign=1_234_000))])
        assert d['2330'] == {'外資': 1234.0, '投信': -200.0, '自營商': 30.0}

    def test_foreign_dealer_nonzero_not_in_any_class(self, monkeypatch):
        a = _t86(monkeypatch, IFX, FIELDS_NOW, [_row(FIELDS_NOW, '2330', _vals(fd=0))])
        b = _t86(monkeypatch, IFX, FIELDS_NOW, [_row(FIELDS_NOW, '2330', _vals(fd=987_000))])
        assert a == b

    def test_guard_mismatch_row_only_nan(self, monkeypatch, capsys):
        rows = [_row(FIELDS_NOW, '2330', _vals()), _row(FIELDS_NOW, '2317', _vals(dealer=99_000))]
        d = _t86(monkeypatch, IFX, FIELDS_NOW, rows)
        assert d['2330']['自營商'] == 30.0
        assert _isnan(d['2317']['自營商']) and d['2317']['外資'] == 5000.0 and d['2317']['投信'] == -200.0
        assert '自行＋避險≠自營商 1 列' in capsys.readouterr().out

    def test_guard_dirty_subcell_unverifiable_nan(self, monkeypatch, capsys):
        v = _vals()
        v['自營商買賣超股數(避險)'] = '--'
        d = _t86(monkeypatch, IFX, FIELDS_NOW, [_row(FIELDS_NOW, '2330', v)])
        assert _isnan(d['2330']['自營商'])
        assert '子欄不可解析 1 列' in capsys.readouterr().out

    def test_no_total_col_sums_subcols(self, monkeypatch):
        f = [c for c in FIELDS_NOW if c != '自營商買賣超股數']
        assert _t86(monkeypatch, IFX, f, [_row(f, '2330', _vals())])['2330']['自營商'] == 30.0

    def test_no_total_col_and_missing_hedge_is_nan(self, monkeypatch):
        f = [c for c in FIELDS_NOW if c not in ('自營商買賣超股數', '自營商買賣超股數(避險)')]
        assert _isnan(_t86(monkeypatch, IFX, f, [_row(f, '2330', _vals())])['2330']['自營商'])

    def test_no_total_col_and_dirty_hedge_is_nan(self, monkeypatch):
        f = [c for c in FIELDS_NOW if c != '自營商買賣超股數']
        v = _vals()
        v['自營商買賣超股數(避險)'] = 'x'
        assert _isnan(_t86(monkeypatch, IFX, f, [_row(f, '2330', v)])['2330']['自營商'])

    def test_total_col_without_subcols(self, monkeypatch):
        f = [c for c in FIELDS_NOW if '(自行買賣)' not in c and '(避險)' not in c]
        assert _t86(monkeypatch, IFX, f, [_row(f, '2330', _vals())])['2330']['自營商'] == 30.0

    @pytest.mark.parametrize('drop, key', [('投信買賣超股數', '投信'),
                                           ('外陸資買賣超股數(不含外資自營商)', '外資')])
    def test_missing_class_column_is_nan(self, drop, key, monkeypatch):
        f = [c for c in FIELDS_NOW if c != drop]
        v = _t86(monkeypatch, IFX, f, [_row(f, '2330', _vals())])['2330']
        assert _isnan(v[key])
        assert all(not _isnan(v[k]) for k in v if k != key)

    def test_no_dealer_columns_is_nan(self, monkeypatch):
        f = [c for c in FIELDS_NOW if not c.startswith('自營商')]
        assert _isnan(_t86(monkeypatch, IFX, f, [_row(f, '2330', _vals())])['2330']['自營商'])

    @pytest.mark.parametrize('dirty', ['--', '', ' ', 'abc', 'N/A'])
    @pytest.mark.parametrize('col, key', [('外陸資買賣超股數(不含外資自營商)', '外資'), ('投信買賣超股數', '投信'),
                                          ('自營商買賣超股數', '自營商')])
    def test_dirty_cell_is_nan_not_zero(self, dirty, col, key, monkeypatch):
        v = _vals()
        v[col] = dirty
        assert _isnan(_t86(monkeypatch, IFX, FIELDS_NOW, [_row(FIELDS_NOW, '2330', v)])['2330'][key])

    def test_real_zero_stays_zero(self, monkeypatch):
        v = _vals(foreign=0, fd=0, trust=0, dself=0, dhedge=0)
        d = _t86(monkeypatch, IFX, FIELDS_NOW, [_row(FIELDS_NOW, '2330', v)])['2330']
        assert d == {'外資': 0.0, '投信': 0.0, '自營商': 0.0}
        assert not any(_isnan(x) for x in d.values())

    def test_signed_and_plus_sign(self, monkeypatch):
        v = _vals()
        v['投信買賣超股數'] = '+1,500'
        assert _t86(monkeypatch, IFX, FIELDS_NOW, [_row(FIELDS_NOW, '2330', v)])['2330']['投信'] == 1.5

    def test_short_row_is_nan(self, monkeypatch):
        row = _row(FIELDS_NOW, '2330', _vals())[:6]
        d = _t86(monkeypatch, IFX, FIELDS_NOW, [row])['2330']
        assert d['外資'] == 5000.0 and _isnan(d['投信']) and _isnan(d['自營商'])

    def test_total_reconciliation_logged_only(self, monkeypatch, capsys):
        d = _t86(monkeypatch, IFX, FIELDS_NOW, [_row(FIELDS_NOW, '2330', _vals(total=1))])
        assert d['2330'] == {'外資': 5000.0, '投信': -200.0, '自營商': 30.0}     # 只 log，不改值
        assert '外資＋投信＋自營商≠三大法人買賣超股數 1 列' in capsys.readouterr().out

    def test_fallback_main_total_nan_propagates(self, monkeypatch):
        rows = [_row(FIELDS_NOW, '2330', _vals(dealer=99_000))]
        _t86(monkeypatch, IFX, FIELDS_NOW, rows)
        base = _dt.date.today()
        df = pd.DataFrame({'date': [base - _dt.timedelta(days=i) for i in range(20)]})
        out = IFX._fetch_twse_inst_fallback('2330', df)
        got = out.dropna(subset=['投信'])
        assert len(got) > 0 and got['自營商'].isna().all() and got['主力合計'].isna().all()

    def test_fallback_main_total_value(self, monkeypatch):
        _t86(monkeypatch, IFX, FIELDS_NOW, [_row(FIELDS_NOW, '2330', _vals())])
        base = _dt.date.today()
        df = pd.DataFrame({'date': [base - _dt.timedelta(days=i) for i in range(20)]})
        got = IFX._fetch_twse_inst_fallback('2330', df).dropna(subset=['投信'])
        assert (got['主力合計'] == 5000.0 - 200.0 + 30.0).all()

    # ── 突變 ────────────────────────────────────────────────────────────────
    def test_pre_fix_self_only_and_fake_zero(self, monkeypatch):
        """突變（整檔還原）：修前自營商只取「自行買賣」⇒ 50.0；髒值／缺投信欄 ⇒ 0.0 假 0 ⇒ 上方斷言轉紅。"""
        pre = z40_pre_module(_DLIF)
        assert _t86(monkeypatch, pre, FIELDS_NOW, [_row(FIELDS_NOW, '2330', _vals())])['2330']['自營商'] == 50.0
        v = _vals()
        v['投信買賣超股數'] = '--'
        assert _t86(monkeypatch, pre, FIELDS_NOW, [_row(FIELDS_NOW, '2330', v)])['2330']['投信'] == 0.0
        f = [c for c in FIELDS_NOW if c != '投信買賣超股數']
        assert _t86(monkeypatch, pre, f, [_row(f, '2330', _vals())])['2330']['投信'] == 0.0

    def test_mutant_substring_dealer_pick_hits_foreign_dealer(self, monkeypatch):
        """單點突變：自營商欄改用子字串 next() ⇒ fd_first 先撿到「外資自營商買賣超股數」⇒ 守衛擋成 NaN（≠ 30）。"""
        m = _mutant_module(_DLIF, [("        d_idx = fi.get(T86_DEALER_NET_COL)\n",
                                    "        d_idx = next((v for k, v in fi.items() if T86_DEALER_NET_COL in k), None)\n")],
                           't86_sub')
        d = _t86(monkeypatch, m, FIELDS_FD_FIRST, [_row(FIELDS_FD_FIRST, '2330', _vals())])['2330']
        assert d['自營商'] != 30.0

    def test_mutant_without_guard(self, monkeypatch):
        """單點突變：拔掉自行＋避險守衛 ⇒ 不一致列照樣回 99.0（≠ NaN）。"""
        m = _mutant_module(_DLIF, [("                if dself_idx is not None and dhedge_idx is not None:\n",
                                    "                if False:\n")], 't86_guard')
        d = _t86(monkeypatch, m, FIELDS_NOW, [_row(FIELDS_NOW, '2317', _vals(dealer=99_000))])['2317']
        assert d['自營商'] == 99.0

    def test_mutant_dirty_cell_back_to_zero(self, monkeypatch):
        """單點突變：_iv 髒值改回 0 ⇒ 髒外資儲存格回 0.0（假 0）。"""
        m = _mutant_module(_DLIF, [("            except (ValueError, TypeError): return None\n",
                                    "            except (ValueError, TypeError): return 0\n")], 't86_dirty')
        v = _vals()
        v['外陸資買賣超股數(不含外資自營商)'] = '--'
        assert _t86(monkeypatch, m, FIELDS_NOW, [_row(FIELDS_NOW, '2330', v)])['2330']['外資'] == 0.0
