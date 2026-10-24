"""C1（DEC-077 第 2 點，客戶 2026-10-24）—— 資料可觀測性：只增加「我們知道資料從哪裡來、是哪一天、清掉多少缺值」的能力。

BACKLOG 5.1.10 三項（⛔ 零投資輸出變更）：
- `DH-C1-NA-DROP-LOG`：8 處 production dropna 之後記「清掉幾筆、哪幾天」（L0 `shared/na_drop_log.py`；清 0 筆不印）。
- `DH-C1-PCR-SRC`：先行指標每日 `_pcr_src`（TAIFEX 官方／FinMind TXO 法人估算）—— 純標記，⛔ 下游不讀。
- `DH-C1-FWD-LEG-ASOF`：前進式驗證帳本附加四欄各腿資料日（schema 純新增、版本維持 3、ruleset_hash 不變）。

還原鏈（本 repo 慣例；寫法照 `tests/test_dec074_revert_chain.py`）：`C1_REVERT_PAIRS` 為「C1 後逐字 → C1 前逐字」，
由 `difflib` 對 `git show 1c8c1415:<檔>`（＝649f7393 產品碼，兩者產品碼逐位相同）與工作樹逐 hunk 產生（最小唯一上下文）；
`C1_BASE_SHA` 寫死以免測試依賴 git。舊批次鏈 `dec074_revert_for`／`z40b_revert_for` 開頭先呼叫 `c1_revert_for`。
⚠️ **只套一次（idempotent）**：判定同 dec074（整檔一起看：全 1 ⇒ 換回；全 0 ⇒ 已換回、原樣返回；其餘 ⇒ AssertionError）。

本檔「C1 前」對照一律用還原體實跑（不讀原始碼字面判行為）；只有零讀者守衛是原始碼掃描（那正是它要守的東西）。
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原組（先於任何 tests.* import 定義 —— dec074／z40b 鏈會回頭 import 本表）
# ══════════════════════════════════════════════════════════════════════════
#: 基底 `1c8c1415`（＝`649f7393` 產品碼）原始檔 sha256（`git show 1c8c1415:<檔> | sha256sum` 實算）。
C1_BASE_SHA = {'scripts/update_macro_forward_test.py': '0c20f5fcb469610658abb78f110bec0fff83420163956ef37d8685a75cf8be55',
 'scripts/update_macro_history.py': '90d46cec4e55d65512de0e934181d2c3f4bcae1c2de4eee0a3a994f820d0c1aa',
 'shared/macro_forward_test_schema.py': '968c48412d6e80a8d5405a3e91674455ac692419179e131bbefb5501c80d4586',
 'src/compute/macro/macro_forward_test.py': '17494d086310eadc0165de4e1255b654e44cebe2d7a505886d6f954ceecf8b64',
 'src/data/daily/daily_data_fetchers.py': 'c69d749d17fa0bb66e9185fb2545253d3c9226c556166b3b4e45d848c7419fff',
 'src/data/macro/leading_indicators.py': 'abe529802db6e91fd382462b162d0954a4cbc97030f7bdc28dbea8ef4d5e792d',
 'src/data/macro/macro_core.py': '2f48071f15b00d5330c33c023089514395c53470edc265fa5f10bf5261a0bc7f',
 'src/data/macro/macro_snapshot.py': '639e527e2f90de3a82a96df56eeaee6c1f2b43e8c2d9b2830a2a92278dc2cf32'}

C1_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'scripts/update_macro_forward_test.py': (('        s.index = pd.DatetimeIndex(pd.to_datetime(df.index))\n'
                                           '        _s_pre_na = s\n'
                                           '        s = s.dropna().sort_index()\n',
                                           '        s.index = pd.DatetimeIndex(pd.to_datetime(df.index))\n'
                                           '        s = s.dropna().sort_index()\n'),
                                          ('        s = s.dropna().sort_index()\n'
                                           '        # C1(DEC-077 第 2 點):只記清掉幾筆／哪幾天(清 0 筆不印);收盤與觀測日不變。\n'
                                           '        from shared.na_drop_log import log_na_drop\n'
                                           '        log_na_drop(_s_pre_na, s, '
                                           "tag='macro_fwd/_twii_close_and_asof', series=f'^TWII:{_col}')\n"
                                           '        if s.empty:\n',
                                           '        s = s.dropna().sort_index()\n        if s.empty:\n'),
                                          ('    from src.compute.macro.macro_forward_test import (\n'
                                           '        build_signal_row, compute_ruleset_hash, '
                                           'leg_as_of_from_inputs, session_has_closed,\n'
                                           '    )\n',
                                           '    from src.compute.macro.macro_forward_test import (\n'
                                           '        build_signal_row, compute_ruleset_hash, '
                                           'session_has_closed,\n'
                                           '    )\n'),
                                          ('    _date = _asof\n'
                                           '    # C1 DH-C1-FWD-LEG-ASOF(DEC-077 第 2 點):各輸入腿資料日 —— '
                                           '純觀測,只寫進帳本四欄,\n'
                                           '    #   ⛔ 不參與任何判斷(上方所有提早結束檢查都已跑完)。函式本身每腿各自 try、不拋例外;\n'
                                           '    #   這裡再包一層:萬一整支失敗,四欄給 None、照樣寫列(觀測欄不得擋下帳本)。\n'
                                           '    try:\n'
                                           '        _leg_as_of = leg_as_of_from_inputs(\n'
                                           "            mkt_info=st.session_state.get('mkt_info') or {},\n"
                                           "            inst=inst, inst_date=bundle.get('inst_date'),\n"
                                           '            df_adl=df_adl, li_latest=df_li)\n'
                                           '    except Exception as _e_leg:  # noqa: BLE001 — 說出來;四欄 '
                                           'None,不影響其餘欄位與是否寫列\n'
                                           "        print(f'[macro_fwd] ⚠️ 各腿資料日取不到({type(_e_leg).__name__}: "
                                           "{_e_leg})→ 四欄記 None,照常寫列')\n"
                                           '        _leg_as_of = None\n'
                                           '    row = build_signal_row(\n',
                                           '    _date = _asof\n    row = build_signal_row(\n'),
                                          ('        date_source=DATE_SOURCE_LIVE,\n'
                                           '        leg_as_of=_leg_as_of,\n'
                                           '    )\n',
                                           '        date_source=DATE_SOURCE_LIVE,\n    )\n')),
 'scripts/update_macro_history.py': (('        })\n'
                                      '        _df_nn = df.dropna(subset=["close"])\n'
                                      '        # C1(DEC-077 第 2 點):只記清掉幾筆／哪幾天(清 0 筆不印);寫入 twii_ohlcv.parquet '
                                      '的內容不變。\n'
                                      '        from shared.na_drop_log import log_na_drop\n'
                                      '        log_na_drop(df, _df_nn, '
                                      "tag='update_macro_history/fetch_twii_ohlcv', series='^TWII',\n"
                                      '                    subset=["close"], date_col="date")\n'
                                      '        df = _df_nn.reset_index(drop=True)\n'
                                      '\n',
                                      '        })\n'
                                      '        df = df.dropna(subset=["close"]).reset_index(drop=True)\n'
                                      '\n'),),
 'shared/macro_forward_test_schema.py': (('    "schema_version",   # int 本 schema 版本,破壞性改欄時 +1\n'
                                          '    # ── 各輸入腿的資料日(C1 DH-C1-FWD-LEG-ASOF,純新增;見下方 '
                                          'MACRO_FWD_TEST_LEG_AS_OF_COLUMNS)──\n'
                                          '    "score_index_as_of",  # str|None \'YYYY-MM-DD\' '
                                          '大盤分(mkt_info)用的 ^TWII 最後一根日期\n'
                                          '    "inst_as_of",         # str|None 外資現貨(inst)資料日;inst 空時 '
                                          'None(失敗時回的是請求日,不是資料日)\n'
                                          '    "adl_as_of",          # str|None 廣度(df_adl)實際被用的那列(末列)日期\n'
                                          '    "li_as_of",           # str|None 先行指標(li_latest)末列 `_date`\n'
                                          ')\n'
                                          '\n'
                                          '#: C1 DH-C1-FWD-LEG-ASOF(DEC-077 第 2 點,客戶 '
                                          '2026-10-24):各輸入腿的資料日,附在\n'
                                          "#: `MACRO_FWD_TEST_HEADERS` 最末。型別 str|None('YYYY-MM-DD',經 "
                                          '`shared.dated_value.iso_date_or_none`)。\n'
                                          '#: **純觀測**:⛔ 不得用這四欄做任何判斷(寫不寫列、改判 '
                                          '⬜、新鮮度…皆禁止);`date`／`inputs_as_of`\n'
                                          '#: 語意與產生方式不變;不回填舊列(DEC-028)。純新增欄 ⇒ 依下方規則 schema 版本**不** bump。\n'
                                          'MACRO_FWD_TEST_LEG_AS_OF_COLUMNS: tuple[str, ...] = (\n'
                                          '    "score_index_as_of", "inst_as_of", "adl_as_of", "li_as_of",\n'
                                          ')\n',
                                          '    "schema_version",   # int 本 schema 版本,破壞性改欄時 +1\n)\n'),
                                         ('#: ⚠️ v2 列與 v3 列**不可混比**（健康分口徑不同）；歷史列的 `schema_version` '
                                          '維持寫入當時的值。\n'
                                          '#: ~~⚠️ 預告（未授權、另批）：計畫第 4 節 `DH-MACRO-FWD-ASOF`（per-leg as_of '
                                          '加欄）若日後實作會再 bump 一次。~~\n'
                                          '#: 📌 2026-10-24 更正（C1 `DH-C1-FWD-LEG-ASOF`，DEC-077 第 2 點；有意識的修改，⛔ '
                                          '不是漏刪；決策者 客戶裁示／\n'
                                          '#:   AI 總管定規格）：per-leg as_of '
                                          '以**純新增欄**落地（`MACRO_FWD_TEST_LEG_AS_OF_COLUMNS`），既有欄語意不變\n'
                                          '#:   ⇒ 依本常數上方規則「純新增欄不必動」**不 bump**（維持 3；`compute_ruleset_hash` '
                                          '不變）。\n'
                                          '#:   舊預告的理由（加欄可能伴隨改 `inputs_as_of` 語意）仍成立，只是那一半**本次未做、仍未授權**：\n'
                                          '#:   若日後改 `inputs_as_of` 語意，屬「改語意」⇒ 屆時仍須 +1。\n'
                                          'MACRO_FWD_TEST_SCHEMA_VERSION: int = 3\n',
                                          '#: ⚠️ v2 列與 v3 列**不可混比**（健康分口徑不同）；歷史列的 `schema_version` '
                                          '維持寫入當時的值。\n'
                                          '#: ⚠️ 預告（未授權、另批）：計畫第 4 節 `DH-MACRO-FWD-ASOF`（per-leg as_of '
                                          '加欄）若日後實作會再 bump 一次。\n'
                                          'MACRO_FWD_TEST_SCHEMA_VERSION: int = 3\n')),
 'src/compute/macro/macro_forward_test.py': (('from datetime import datetime, time, timedelta, timezone\n'
                                              'from typing import Any, Iterable, Mapping, Optional, Union\n'
                                              '\n',
                                              'from datetime import datetime, time, timedelta, timezone\n'
                                              'from typing import Any, Iterable, Optional, Union\n'
                                              '\n'),
                                             ('\n'
                                              'from shared.dated_value import iso_date_or_none  # C1 '
                                              'DH-C1-FWD-LEG-ASOF:日期收斂 SSOT(L0)\n'
                                              'from shared.macro_forward_test_schema import (\n',
                                              '\nfrom shared.macro_forward_test_schema import (\n'),
                                             ('    MACRO_FWD_TEST_HEADERS,\n'
                                              '    MACRO_FWD_TEST_LEG_AS_OF_COLUMNS,\n'
                                              '    MACRO_FWD_TEST_SCHEMA_VERSION,\n',
                                              '    MACRO_FWD_TEST_HEADERS,\n'
                                              '    MACRO_FWD_TEST_SCHEMA_VERSION,\n'),
                                             ('    date_source: Optional[str] = None,\n'
                                              '    leg_as_of: Optional[Mapping] = None,\n'
                                              ') -> dict[str, Any]:\n',
                                              '    date_source: Optional[str] = None,\n'
                                              ') -> dict[str, Any]:\n'),
                                             ('        git_sha / ruleset_hash: caller 注入(git 查詢是 I/O,不屬 '
                                              'L2)。\n'
                                              '        leg_as_of: C1 `DH-C1-FWD-LEG-ASOF` —— '
                                              '各輸入腿資料日(`leg_as_of_from_inputs` 的回傳);\n'
                                              '            鍵只能是 `MACRO_FWD_TEST_LEG_AS_OF_COLUMNS`,缺的鍵 / '
                                              'None ⇒ 該欄 None。\n'
                                              '            **純觀測**:只原樣寫進四欄,⛔ 不參與任何判斷(其餘欄位與檢查一字不改)。\n'
                                              '\n',
                                              '        git_sha / ruleset_hash: caller 注入(git 查詢是 I/O,不屬 '
                                              'L2)。\n'
                                              '\n'),
                                             ('    }\n'
                                              '    # C1 DH-C1-FWD-LEG-ASOF:各腿資料日四欄(純新增,附在最末;⛔ 不參與任何判斷)。\n'
                                              '    _leg = dict(leg_as_of or {})\n'
                                              '    _leg_unknown = set(_leg) - '
                                              'set(MACRO_FWD_TEST_LEG_AS_OF_COLUMNS)\n'
                                              '    if _leg_unknown:\n'
                                              "        raise ValueError(f'build_signal_row: leg_as_of "
                                              "含不認得的鍵:{sorted(map(str, _leg_unknown))}')\n"
                                              '    for _k in MACRO_FWD_TEST_LEG_AS_OF_COLUMNS:\n'
                                              '        row[_k] = (str(_leg[_k]) if _leg.get(_k) else None)\n'
                                              '    _unknown = set(row) - set(MACRO_FWD_TEST_HEADERS)\n',
                                              '    }\n'
                                              '    _unknown = set(row) - set(MACRO_FWD_TEST_HEADERS)\n'),
                                             ('    return row\n'
                                              '\n'
                                              '\n'
                                              'def leg_as_of_from_inputs(*, mkt_info: Any, inst: Any, '
                                              'inst_date: Any,\n'
                                              '                          df_adl: Any, li_latest: Any) -> '
                                              'dict[str, Optional[str]]:\n'
                                              '    """C1 `DH-C1-FWD-LEG-ASOF`(DEC-077 第 2 點):各輸入腿的資料日 → '
                                              "`{四欄: 'YYYY-MM-DD'|None}`。\n"
                                              '\n'
                                              "    - `score_index_as_of` ← `mkt_info['index_as_of']`(大盤分用的 "
                                              '^TWII 最後一根);\n'
                                              '    - `inst_as_of` ← `inst_date`,**只在 `inst` '
                                              '非空時**(`fetch_institutional` 失敗回的是請求日、\n'
                                              '      不是資料日 ⇒ inst 空時一律 None);\n'
                                              "    - `adl_as_of` ← `df_adl['date'].iloc[-1]`(實際被用的那列);\n"
                                              "    - `li_as_of` ← `li_latest.iloc[-1]['_date']`。\n"
                                              '\n'
                                              '    一律經 `shared.dated_value.iso_date_or_none` 收斂(解析不了 ⇒ '
                                              'None,⛔ 不猜、不拿今天頂替)。\n'
                                              '    每腿各自 try:失敗 print 原因並給 None。**絕不拋例外、不改傳入物件**;純觀測,⛔ '
                                              '不得用於任何判斷。\n'
                                              '    """\n'
                                              '    def _score():\n'
                                              "        return mkt_info.get('index_as_of') if "
                                              'isinstance(mkt_info, Mapping) else None\n'
                                              '\n'
                                              '    def _inst():\n'
                                              '        return inst_date if (inst is not None and len(inst) > '
                                              '0) else None\n'
                                              '\n'
                                              '    def _adl():\n'
                                              '        if df_adl is None or len(df_adl) == 0:\n'
                                              '            return None\n'
                                              "        return df_adl['date'].iloc[-1]\n"
                                              '\n'
                                              '    def _li():\n'
                                              '        if li_latest is None or len(li_latest) == 0:\n'
                                              '            return None\n'
                                              "        return li_latest.iloc[-1]['_date']\n"
                                              '\n'
                                              '    out: dict[str, Optional[str]] = {}\n'
                                              '    for _col, _fn in zip(MACRO_FWD_TEST_LEG_AS_OF_COLUMNS, '
                                              '(_score, _inst, _adl, _li)):\n'
                                              '        try:\n'
                                              '            out[_col] = iso_date_or_none(_fn())\n'
                                              '        except Exception as _e:  # noqa: BLE001 — '
                                              '單腿失敗只影響該欄(None),說出來,不中斷落地\n'
                                              "            print(f'[macro_forward_test/leg_as_of] {_col} "
                                              "取不到({type(_e).__name__}: {_e})→ None')\n"
                                              '            out[_col] = None\n'
                                              '    return out\n'
                                              '\n',
                                              '    return row\n\n')),
 'src/data/daily/daily_data_fetchers.py': (('from shared.inst_labels import is_foreign_dealer_label  # 批 Z40 '
                                            '法人身分別判定 SSOT(L0)\n'
                                            'from shared.na_drop_log import log_na_drop  # C1 '
                                            'DH-C1-NA-DROP-LOG:dropna 清理筆數 log(L0,純觀測)\n'
                                            'from src.config import TTL_CONFIG as _TTL_CFG\n',
                                            'from shared.inst_labels import is_foreign_dealer_label  # 批 Z40 '
                                            '法人身分別判定 SSOT(L0)\n'
                                            'from src.config import TTL_CONFIG as _TTL_CFG\n'),
                                           ("        if 'close' in h.columns:\n"
                                            '            _h_pre_na = h\n'
                                            "            h = h.dropna(subset=['close'])\n",
                                            "        if 'close' in h.columns:\n"
                                            "            h = h.dropna(subset=['close'])\n"),
                                           ("            h = h.dropna(subset=['close'])\n"
                                            '            # C1(DEC-077 第 2 點):只記清掉幾筆／哪幾天,dropna 與回傳不變;清 0 '
                                            '筆不印。\n'
                                            '            log_na_drop(_h_pre_na, h, '
                                            "tag='daily_data_fetchers/_fetch_single_cached',\n"
                                            "                        series=str(symbol), subset=['close'])\n"
                                            "        elif 'Close' in h.columns:\n",
                                            "            h = h.dropna(subset=['close'])\n"
                                            "        elif 'Close' in h.columns:\n"),
                                           ('                _twii.columns = '
                                            '_twii.columns.get_level_values(0)\n'
                                            '            _twii_pre_na = _twii\n'
                                            "            _twii = _twii.dropna(subset=['Close'])\n",
                                            '                _twii.columns = '
                                            '_twii.columns.get_level_values(0)\n'
                                            "            _twii = _twii.dropna(subset=['Close'])\n"),
                                           ("            _twii = _twii.dropna(subset=['Close'])\n"
                                            '            # C1(DEC-077 第 2 點):清理筆數只走 stdout(⛔ 不寫 '
                                            'ADL_LOG_PATH,UI 會讀);清 0 筆不印。\n'
                                            '            log_na_drop(_twii_pre_na, _twii, '
                                            "tag='daily_data_fetchers/fetch_adl',\n"
                                            "                        series='^TWII', subset=['Close'])\n"
                                            '            for _ix in _twii.index:\n',
                                            "            _twii = _twii.dropna(subset=['Close'])\n"
                                            '            for _ix in _twii.index:\n')),
 'src/data/macro/leading_indicators.py': (('_MTX_TO_TX_FACTOR = 0.25\n'
                                           '\n'
                                           '# ════════════════════════════════════════════════════════\n'
                                           '# C1 DH-C1-PCR-SRC(DEC-077 第 2 點,客戶 '
                                           '2026-10-24):每日「選PCR」的來源標記(純觀測)\n'
                                           '# ════════════════════════════════════════════════════════\n'
                                           '# 「選PCR」同一欄混著兩種來源:TAIFEX 官方 pcRatio(全市場)與 FinMind TXO 三大法人 OI '
                                           '估算\n'
                                           '# (只算法人部位,是代理估算)。修前整表只有一個 `source` 字串,分不出**某一天**是哪一種。\n'
                                           '# 本欄只描述來源,⛔ **不是計分資格**:值、覆蓋順序、門檻、燈號、快取鍵、LI_VERSION、整表\n'
                                           '# `source` 字串、`dated_inputs.SRC_PCR` 全部不變;⛔ **任何下游不得讀 '
                                           '`_pcr_src`**\n'
                                           '# (守衛:tests/test_c1_observability.py 零讀者測試)。欄名底線開頭 ⇒ '
                                           'section_chips CSV 匯出\n'
                                           '# 規則(底線 = 內部 marker)自動排除,使用者下載的 CSV 不會多一欄。\n'
                                           '# 不變式:`_pcr_src` 為 None ⟺ `選PCR` 為 None。舊 pickle 快取沒有這一欄(不回填)。\n'
                                           'PCR_SRC_COL = "_pcr_src"\n'
                                           'PCR_SRC_TAIFEX = "TAIFEX"                       # TAIFEX pcRatio '
                                           '官方值(全市場)\n'
                                           'PCR_SRC_FINMIND_EST = "FinMind-TXO-inst-est"    # FinMind TXO '
                                           '三大法人 OI 估算(代理)\n'
                                           'from types import MappingProxyType as _MappingProxyType  # noqa: '
                                           'E402\n'
                                           '#: 來源種類(只描述來源,⛔ 不是計分資格)。\n'
                                           'PCR_SRC_KIND = _MappingProxyType({PCR_SRC_TAIFEX: "official",\n'
                                           '                                  PCR_SRC_FINMIND_EST: '
                                           '"proxy_estimate"})\n'
                                           '\n',
                                           '_MTX_TO_TX_FACTOR = 0.25\n\n'),
                                          ('            "未平倉口數":lt.get("未平倉"), "韭菜指數":mtx_data.get(d),\n'
                                           '            # C1 DH-C1-PCR-SRC:本路徑 PCR 只有 TAIFEX '
                                           '一種來源(純觀測,下游不讀)。\n'
                                           '            PCR_SRC_COL: (PCR_SRC_TAIFEX if pcr_dict.get(d) is '
                                           'not None else None),\n'
                                           '        })\n',
                                           '            "未平倉口數":lt.get("未平倉"), "韭菜指數":mtx_data.get(d),\n'
                                           '        })\n'),
                                          ('    pcr_dict = {}\n'
                                           '    pcr_src = {}   # C1 DH-C1-PCR-SRC:{ymd: PCR_SRC_*} —— '
                                           '只描述來源,不進 known/target、不影響任何值\n'
                                           '    opt_dict = {}\n',
                                           '    pcr_dict = {}\n    opt_dict = {}\n'),
                                          ('                pcr_dict[dk] = round(b["putV"] / b["callV"] * '
                                           '100, 1)\n'
                                           '                pcr_src[dk] = PCR_SRC_FINMIND_EST\n'
                                           '            opt_dict[dk] = round((b["extBC"] - b["extSC"] - '
                                           'b["extBP"] + b["extSP"]) / 10)\n',
                                           '                pcr_dict[dk] = round(b["putV"] / b["callV"] * '
                                           '100, 1)\n'
                                           '            opt_dict[dk] = round((b["extBC"] - b["extSC"] - '
                                           'b["extBP"] + b["extSP"]) / 10)\n'),
                                          ('            pcr_dict.update(pcr_taifex)\n'
                                           '            pcr_src.update(dict.fromkeys(pcr_taifex, '
                                           'PCR_SRC_TAIFEX))   # C1:同一批鍵改標 TAIFEX\n'
                                           '            print(f"[LI-v8] PCR(TAIFEX精確) {len(pcr_taifex)} 天 → '
                                           '覆蓋 FinMind 估算")\n',
                                           '            pcr_dict.update(pcr_taifex)\n'
                                           '            print(f"[LI-v8] PCR(TAIFEX精確) {len(pcr_taifex)} 天 → '
                                           '覆蓋 FinMind 估算")\n'),
                                          ('            "融券餘額":   margin_dict.get(d, {}).get(\'融券餘額\'),\n'
                                           '            # C1 DH-C1-PCR-SRC(純觀測,⛔ 下游不讀):選PCR 為 None ⇒ 一律 '
                                           'None(不變式)。\n'
                                           '            PCR_SRC_COL:  (pcr_src.get(d) if pcr_dict.get(d) is '
                                           'not None else None),\n'
                                           '        })\n',
                                           '            "融券餘額":   margin_dict.get(d, {}).get(\'融券餘額\'),\n'
                                           '        })\n')),
 'src/data/macro/macro_core.py': (('from shared.fail_cooldown import FAIL_COOLDOWN_SEC as '
                                   '_FAIL_COOLDOWN_SEC  # Q2-r2 2026-09-27\n'
                                   'from shared.na_drop_log import log_na_drop  # C1 '
                                   'DH-C1-NA-DROP-LOG:dropna 清理筆數 log(L0,純觀測)\n'
                                   '\n',
                                   'from shared.fail_cooldown import FAIL_COOLDOWN_SEC as '
                                   '_FAIL_COOLDOWN_SEC  # Q2-r2 2026-09-27\n'
                                   '\n'),
                                  ('        close = result["indicators"]["quote"][0]["close"]\n'
                                   '        _s_pre_na = pd.Series(close, index=pd.to_datetime(ts, unit="s"), '
                                   'dtype=float)\n'
                                   '        s = _s_pre_na.dropna()\n'
                                   '        # C1(DEC-077 第 2 點):只記清掉幾筆／哪幾天(清 0 筆不印);回傳、快取、退避不變。\n'
                                   "        log_na_drop(_s_pre_na, s, tag='macro_core/_fetch_yf_close_base', "
                                   'series=str(ticker))\n'
                                   '        s.name = ticker\n',
                                   '        close = result["indicators"]["quote"][0]["close"]\n'
                                   '        s = pd.Series(close, index=pd.to_datetime(ts, unit="s"), '
                                   'dtype=float).dropna()\n'
                                   '        s.name = ticker\n'),
                                  ('        }, index=ts)\n'
                                   '        _df_pre_na = df\n'
                                   '        df = df.dropna(subset=["Close"])\n',
                                   '        }, index=ts)\n        df = df.dropna(subset=["Close"])\n'),
                                  ('        df = df.dropna(subset=["Close"])\n'
                                   '        # C1(DEC-077 第 2 點):只記清掉幾筆／哪幾天(清 0 筆不印);回傳、退避不變。\n'
                                   "        log_na_drop(_df_pre_na, df, tag='macro_core/fetch_yf_ohlcv',\n"
                                   "                    series=f'{ticker}:{range_}:{interval}', "
                                   'subset=["Close"])\n'
                                   '        # S-PROV-1 phase 16 v18.262 — provenance(schema-additive)\n',
                                   '        df = df.dropna(subset=["Close"])\n'
                                   '        # S-PROV-1 phase 16 v18.262 — provenance(schema-additive)\n')),
 'src/data/macro/macro_snapshot.py': (('from shared.vix_validity import VIX_FETCH_MAX, vix_value_or_none  # '
                                       '批 Z13(Q-r8b ②)\n'
                                       'from shared.na_drop_log import log_na_drop  # C1 '
                                       'DH-C1-NA-DROP-LOG:dropna 清理筆數 log(L0,純觀測)\n'
                                       'import math\n',
                                       'from shared.vix_validity import VIX_FETCH_MAX, vix_value_or_none  # '
                                       '批 Z13(Q-r8b ②)\n'
                                       'import math\n'),
                                      ('            _df_v.columns = _df_v.columns.get_level_values(0)\n'
                                       '        _df_v_pre_na = _df_v\n'
                                       "        _df_v = _df_v.dropna(subset=['Close'])\n",
                                       '            _df_v.columns = _df_v.columns.get_level_values(0)\n'
                                       "        _df_v = _df_v.dropna(subset=['Close'])\n"),
                                      ("        _df_v = _df_v.dropna(subset=['Close'])\n"
                                       '        # C1(DEC-077 第 2 點):NaN 清理筆數 log(清 0 筆不印);下方非有限值剔除的既有計數不動。\n'
                                       '        log_na_drop(_df_v_pre_na, _df_v, '
                                       "tag='macro_snapshot/fetch_vix_block',\n"
                                       "                    series='^VIX', subset=['Close'])\n"
                                       '        # 批 V2(V1-n3 根源,三類 (c)):末筆 ±inf 不放行 → 落到下方既有失敗出口\n',
                                       "        _df_v = _df_v.dropna(subset=['Close'])\n"
                                       '        # 批 V2(V1-n3 根源,三類 (c)):末筆 ±inf 不放行 → 落到下方既有失敗出口\n'),
                                      ('            return None\n'
                                       '    _cs_pre_na = _twii[_cc_b]\n'
                                       '    _cs = _cs_pre_na.dropna()\n'
                                       '    # C1(DEC-077 第 2 點):只記清掉幾筆／哪幾天(清 0 筆不印);乖離、as_of 不變。\n'
                                       '    log_na_drop(_cs_pre_na, _cs, '
                                       "tag='macro_snapshot/compute_twii_bias', series=f'^TWII:{_cc_b}')\n"
                                       '    _n = len(_cs)\n',
                                       '            return None\n'
                                       '    _cs = _twii[_cc_b].dropna()\n'
                                       '    _n = len(_cs)\n'))}



def _rel(file_path) -> str:
    p = pathlib.Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def c1_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 C1 之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = C1_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回（每組 `新寫法` 都含 C1 新增行，換回後必然 0 次）
    assert all(c == 1 for c in counts), (
        f"{rel} C1 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new[:120]!r}"
        code = code.replace(new, old)
    return code


def _exec_as_module(rel: str, code: str, name: str, *, swap: dict | None = None):
    """原始碼 → 獨立模組物件（不影響本尊）。`swap`：exec 期間暫換的 sys.modules 項（例：換成 C1 前 schema）。

    exec 期間 `@monitored` 會重新登錄同名 fetcher（重設其狀態欄）⇒ 前後快照還原 `_MONITOR_REGISTRY`，不污染別的測試。
    """
    from shared import fetch_monitor as _fm
    path = REPO / rel
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(path)
    sys.modules[name] = m                      # dataclass 等需要以模組名回查
    _reg = {k: dict(v) for k, v in _fm._MONITOR_REGISTRY.items()}
    _saved = {k: sys.modules.get(k) for k in (swap or {})}
    try:
        for k, v in (swap or {}).items():
            sys.modules[k] = v
        exec(compile(code, str(path), "exec"), m.__dict__)
    finally:
        for k, v in _saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        _fm._MONITOR_REGISTRY.clear()
        _fm._MONITOR_REGISTRY.update(_reg)
    return m


_PRE_CACHE: dict = {}


def c1_pre_module(rel: str):
    """現行檔只把 C1 改動換回基底 `1c8c1415` 寫法（獨立模組物件）。

    `src/compute/macro/macro_forward_test.py` 會連同 C1 前的 schema 一起換（`from shared.macro_forward_test_schema
    import …` 綁到 C1 前常數），其餘檔只換自己。
    """
    if rel in _PRE_CACHE:
        return _PRE_CACHE[rel]
    swap = None
    if rel == "src/compute/macro/macro_forward_test.py":
        swap = {"shared.macro_forward_test_schema": c1_pre_module("shared/macro_forward_test_schema.py")}
    code = c1_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
    m = _exec_as_module(rel, code, "_c1_pre_" + rel.replace("/", "_").removesuffix(".py"), swap=swap)
    _PRE_CACHE[rel] = m
    return m


def c1_mutant_module(rel: str, swaps, tag: str):
    """單點突變：現行檔做指定替換（每組恰一處）後載入成獨立模組。"""
    code = (REPO / rel).read_text(encoding="utf-8")
    for new, old in swaps:
        assert code.count(new) == 1, f"突變點不唯一或已不存在：{new[:100]!r}"
        code = code.replace(new, old)
    return _exec_as_module(rel, code, f"_c1_mut_{tag}")


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案與舊批次測試
# ══════════════════════════════════════════════════════════════════════════
import copy  # noqa: E402
import datetime as dt  # noqa: E402
import itertools  # noqa: E402
import os  # noqa: E402
import pickle  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

_LI = "src/data/macro/leading_indicators.py"
_SCHEMA = "shared/macro_forward_test_schema.py"
_MFT = "src/compute/macro/macro_forward_test.py"
_DDF = "src/data/daily/daily_data_fetchers.py"
_MC = "src/data/macro/macro_core.py"
_MSN = "src/data/macro/macro_snapshot.py"
_CRON = "scripts/update_macro_forward_test.py"
_UMH = "scripts/update_macro_history.py"
_TW = timezone(timedelta(hours=8))
_uid = itertools.count()


# ══════════════════════════════════════════════════════════════════════════
# 1. 還原鏈
# ══════════════════════════════════════════════════════════════════════════
def test_c1_revert_is_exact_base_source():
    """還原體逐位 ＝ 基底 `1c8c1415` ⇒ 本檔「C1 前」對照跑的是真 C1 前碼。"""
    assert set(C1_REVERT_PAIRS) == set(C1_BASE_SHA)
    for rel in sorted(C1_REVERT_PAIRS):
        code = c1_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == C1_BASE_SHA[rel], rel


def test_c1_revert_is_idempotent():
    for rel in sorted(C1_REVERT_PAIRS):
        once = c1_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert c1_revert_for(rel, once) == once, rel


def test_older_chains_start_with_c1():
    """舊批次鏈（dec074／z40b）已先串 C1 ⇒ 它們的基底 sha 守衛不因 C1 轉紅。"""
    from tests.test_dec074_revert_chain import DEC074_BASE_SHA, dec074_revert_for
    from tests.test_batch_z40b import Z40B_BASE_SHA, z40b_revert_for
    for rel in (_SCHEMA, _MFT):
        code = dec074_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == DEC074_BASE_SHA[rel], rel
    code = z40b_revert_for(_LI, (REPO / _LI).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z40B_BASE_SHA[_LI]


# ══════════════════════════════════════════════════════════════════════════
# 2. DH-C1-NA-DROP-LOG
# ══════════════════════════════════════════════════════════════════════════
_C1_MARK = "⚠️ 缺值清理："


def _c1_lines(out: str) -> list[str]:
    return [ln for ln in out.splitlines() if _C1_MARK in ln]


def _strip_c1(out: str) -> str:
    return "".join(ln for ln in out.splitlines(keepends=True) if _C1_MARK not in ln)


class TestNaDropHelper:
    def test_prints_only_when_rows_dropped(self, capsys):
        from shared.na_drop_log import log_na_drop
        idx = pd.date_range("2026-10-01", periods=4)
        df = pd.DataFrame({"close": [1.0, np.nan, 3.0, np.nan]}, index=idx)
        log_na_drop(df, df.dropna(subset=["close"]), tag="t/f", series="^X", subset=["close"])
        out = capsys.readouterr().out
        assert out == ("[t/f] ⚠️ 缺值清理：^X 清掉 2 筆收盤為空值的列"
                       "（日期樣本：2026-10-02、2026-10-04；含最新一根：是）\n")
        clean = df.dropna()
        log_na_drop(clean, clean.dropna(), tag="t/f", series="^X")
        assert capsys.readouterr().out == ""

    def test_sample_cap_and_latest_flag(self):
        from shared.na_drop_log import NA_DROP_SAMPLE_N, na_drop_note
        idx = pd.date_range("2026-10-01", periods=9)
        s = pd.Series([np.nan] * 7 + [1.0, 2.0], index=idx)
        msg = na_drop_note(s, s.dropna(), tag="a", series="b")
        assert "共 7 筆" in msg and msg.count("2026-10-0") == NA_DROP_SAMPLE_N
        assert "含最新一根：否" in msg

    def test_date_column_and_unsorted_index(self):
        from shared.na_drop_log import na_drop_note
        df = pd.DataFrame({"date": [dt.date(2026, 10, 3), dt.date(2026, 10, 1), dt.date(2026, 10, 2)],
                           "close": [np.nan, 1.0, 2.0]})
        msg = na_drop_note(df, df.dropna(subset=["close"]), tag="u", series="v",
                           subset=["close"], date_col="date")
        assert "日期樣本：2026-10-03；含最新一根：是" in msg

    @pytest.mark.parametrize("before, after", [
        (None, None), (object(), []), (pd.DataFrame({"x": [1]}), pd.DataFrame()),
    ], ids=["none", "no-len", "df-sample-fails"])
    def test_never_raises(self, before, after):
        from shared.na_drop_log import log_na_drop, na_drop_note
        msg = na_drop_note(before, after, tag="z", series="z", subset=["close"])
        assert msg is None or "取不到" in msg
        log_na_drop(before, after, tag="z", series="z", subset=["close"])

    def test_does_not_mutate_inputs(self):
        from shared.na_drop_log import na_drop_note
        df = pd.DataFrame({"close": [1.0, np.nan]}, index=pd.date_range("2026-10-01", periods=2))
        snap = df.copy(deep=True)
        after = df.dropna()
        na_drop_note(df, after, tag="a", series="b", subset=["close"])
        pd.testing.assert_frame_equal(df, snap)

    def test_message_does_not_collide_with_existing_wording(self):
        """措辭不得與既有字串相撞（例：VIX 的「剔除中段」計數）。"""
        from shared.na_drop_log import na_drop_note
        s = pd.Series([np.nan, 1.0], index=pd.date_range("2026-10-01", periods=2))
        assert "剔除中段" not in na_drop_note(s, s.dropna(), tag="a", series="b")


def _weekdays(n: int, end: dt.date | None = None) -> list[dt.date]:
    out, d = [], (end or dt.date.today())
    while len(out) < n:
        d -= dt.timedelta(days=1)
        if d.weekday() < 5:
            out.append(d)
    return sorted(out)


def _nan_idx(n: int, nan_at) -> set:
    """nan_at 內的負數 = 從尾端數（-1 ＝ 最後一根）。"""
    return {i % n for i in nan_at}


def _closes(n: int, nan_at=()) -> list:
    _ix = _nan_idx(n, nan_at)
    return [np.nan if i in _ix else 100.0 + i for i in range(n)]


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


def _chart_payload(days, closes):
    ts = [int(datetime(d.year, d.month, d.day, 1, 30, tzinfo=timezone.utc).timestamp()) for d in days]
    n = len(days)
    return {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [{
        "open": [99.0] * n, "high": [120.0] * n, "low": [90.0] * n,
        "close": list(closes), "volume": [1000] * n}]}}]}}


def _strip_keys(x, keys=("fetched_at",)):
    if isinstance(x, dict):
        return {k: _strip_keys(v, keys) for k, v in x.items() if k not in keys}
    return x


# ── 各處 harness：(module) → 回傳值；呼叫端負責 capsys ─────────────────────────
def _site_fetch_single(mod, mp, nan_at, tk):
    days = _weekdays(8)
    raw = pd.DataFrame({"Open": _closes(8), "High": _closes(8), "Low": _closes(8),
                        "Close": _closes(8, nan_at), "Volume": [1] * 8},
                       index=pd.DatetimeIndex([pd.Timestamp(d) for d in days]))
    mp.setattr(mod, "_history_with_status", lambda hist, sym, period: (raw.copy(), False))
    mp.setattr(mod, "_pkl_get", lambda *a, **k: mod._CACHE_SENTINEL)
    mp.setattr(mod, "_pkl_put", lambda *a, **k: None)
    mp.setattr(mod, "_prov_log", lambda *a, **k: None)
    return mod._fetch_single_cached.__wrapped__(tk, "60d")


def _site_fetch_adl(mod, mp, nan_at, tk, tmp_path):
    import shared.cache_layer as CL
    import yfinance
    # ⚠️ 打在實作模組上（`src.data.stock` 是 PEP 562 轉發 package；直接 setattr package 會在還原後留下一個
    #   遮蔽 `__getattr__` 的實體屬性，污染之後以 TSF 為準 monkeypatch 的測試）。
    import src.data.stock.tw_stock_data_fetcher as TSF
    sub = tmp_path / f"adl{next(_uid)}"
    sub.mkdir()
    mp.setattr(CL, "_PKL_DIR", str(sub))
    mp.setattr(CL, "ADL_LOG_PATH", str(sub / "adl.log"))
    mp.setattr(TSF, "_load_proxy_config", lambda: {})
    days = _weekdays(10)
    raw = pd.DataFrame({"Open": [100.0] * 10, "Close": _closes(10, nan_at)},
                       index=pd.DatetimeIndex([pd.Timestamp(d) for d in days]))
    mp.setattr(yfinance, "download", lambda *a, **k: raw.copy())
    out = mod.fetch_adl.__wrapped__(days=60)
    return out, (sub / "adl.log").read_text(encoding="utf-8")


def _site_yf_ohlcv(mod, mp, nan_at, tk):
    days = _weekdays(8)
    mp.setattr(mod, "fetch_url", lambda *a, **k: _Resp(_chart_payload(days, _closes(8, nan_at))))
    df = mod.fetch_yf_ohlcv(tk, range_="9mo")
    return df.drop(columns=["fetched_at"], errors="ignore")


def _site_yf_close(mod, mp, nan_at, tk):
    days = _weekdays(8)
    mp.setattr(mod, "fetch_url", lambda *a, **k: _Resp(_chart_payload(days, _closes(8, nan_at))))
    s = mod._fetch_yf_close_base(tk)
    return s.copy(), s.attrs.get("source")      # attrs 的 fetched_at 是抓取時刻，不比


def _site_twii_bias(mod, mp, nan_at, tk):
    days = pd.bdate_range(end=pd.Timestamp("2026-10-23"), periods=260)
    df = pd.DataFrame({"Close": [20000.0 + i for i in range(260)]}, index=days)
    for i in _nan_idx(260, nan_at):
        df.iloc[i, 0] = np.nan
    return mod.compute_twii_bias(df)


def _site_vix(mod, mp, nan_at, tk):
    import yfinance
    days = _weekdays(25)
    raw = pd.DataFrame({"Close": [15.0 + 0.1 * i if i not in _nan_idx(25, nan_at) else np.nan
                                  for i in range(25)]},
                       index=pd.DatetimeIndex([pd.Timestamp(d) for d in days]))
    mp.setattr(yfinance, "download", lambda *a, **k: raw.copy())
    return _strip_keys(mod.fetch_vix_block.__wrapped__())


def _site_cron_twii(mod, mp, nan_at, tk):
    days = _weekdays(8)
    df = pd.DataFrame({"close": _closes(8, nan_at)}, index=pd.to_datetime(days))
    return mod._twii_close_and_asof({"台股加權指數": df})


def _site_umh_twii(mod, mp, nan_at, tk):
    days = _weekdays(8)
    mp.setattr(mod, "_fetch_url_via_proxy", lambda *a, **k: _Resp(_chart_payload(days, _closes(8, nan_at))))
    return mod.fetch_twii_ohlcv(days[0], days[-1]).drop(columns=["fetched_at"], errors="ignore")


_SITES = {
    "fetch_single": (_DDF, _site_fetch_single, "daily_data_fetchers/_fetch_single_cached"),
    "fetch_adl": (_DDF, _site_fetch_adl, "daily_data_fetchers/fetch_adl"),
    "yf_ohlcv": (_MC, _site_yf_ohlcv, "macro_core/fetch_yf_ohlcv"),
    "yf_close": (_MC, _site_yf_close, "macro_core/_fetch_yf_close_base"),
    "twii_bias": (_MSN, _site_twii_bias, "macro_snapshot/compute_twii_bias"),
    "vix": (_MSN, _site_vix, "macro_snapshot/fetch_vix_block"),
    "cron_twii": (_CRON, _site_cron_twii, "macro_fwd/_twii_close_and_asof"),
    "umh_twii": (_UMH, _site_umh_twii, "update_macro_history/fetch_twii_ohlcv"),
}


def _current_module(rel):
    import importlib
    name = rel.removesuffix(".py").replace("/", ".")
    return importlib.import_module(name)


def _assert_same(a, b):
    if isinstance(a, tuple) and isinstance(b, tuple):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            _assert_same(x, y)
    elif isinstance(a, pd.DataFrame):
        pd.testing.assert_frame_equal(a, b)
    elif isinstance(a, pd.Series):
        pd.testing.assert_series_equal(a, b)
    else:
        assert a == b


@pytest.mark.parametrize("site", sorted(_SITES))
@pytest.mark.parametrize("nan_at", [(), (2, 5), (-1,)], ids=["clean", "mid-nan", "last-nan"])
def test_na_drop_log_per_site(site, nan_at, monkeypatch, tmp_path, capsys):
    """每處：清 >0 筆才印一行（含 tag／筆數），清 0 筆 stdout 與 C1 前逐字相同；回傳值與 C1 前相同。

    「C1 前」＝ `c1_revert_for` 還原體實跑 ⇒ 同時是本項的突變測試（拔掉新增 log 時第一個斷言轉紅）。
    """
    rel, fn, tag = _SITES[site]
    extra = (tmp_path,) if site == "fetch_adl" else ()
    new_mod, pre_mod = _current_module(rel), c1_pre_module(rel)
    capsys.readouterr()
    tk = f"C1T{next(_uid)}"                       # 新舊兩邊同一個代號（各自模組的快取互不相干）
    new_ret = fn(new_mod, monkeypatch, nan_at, tk, *extra)
    new_out = capsys.readouterr().out
    pre_ret = fn(pre_mod, monkeypatch, nan_at, tk, *extra)
    pre_out = capsys.readouterr().out
    if site == "fetch_adl":   # ⛔ 不寫 ADL_LOG_PATH（UI 會讀）：log 檔逐字與 C1 前相同
        (new_ret, new_log), (pre_ret, pre_log) = new_ret, pre_ret
        assert _C1_MARK not in new_log and new_log == pre_log
    lines = _c1_lines(new_out)
    if nan_at:
        assert len(lines) == 1, new_out
        assert lines[0].startswith(f"[{tag}] {_C1_MARK}"), lines[0]
        assert f"清掉 {len(nan_at)} 筆" in lines[0]
        assert ("含最新一根：是" in lines[0]) == (-1 in nan_at)
        assert _c1_lines(pre_out) == []                 # 突變（拔掉 log）⇒ 上面 len==1 轉紅
    else:
        assert lines == []
    assert _strip_c1(new_out) == pre_out                 # 其餘 stdout 逐字不變（清 0 筆時＝整份相同）
    _assert_same(new_ret, pre_ret)


def test_fetch_single_dead_close_branch_untouched():
    """`_fetch_single_cached` 的 `elif 'Close'` 分支（欄名已先小寫化 ⇒ 死碼）規格明訂不動。"""
    src = (REPO / _DDF).read_text(encoding="utf-8")
    assert "        elif 'Close' in h.columns:\n            h = h.dropna(subset=['Close'])\n" in src


# ══════════════════════════════════════════════════════════════════════════
# 3. DH-C1-PCR-SRC
# ══════════════════════════════════════════════════════════════════════════
_LD = _weekdays(5)
_LDK = [d.strftime("%Y%m%d") for d in _LD]


def _fut_frame():
    rows = []
    for d in _LD:
        rows.append(dict(date=d.isoformat(), institutional_investors="外資",
                         long_open_interest_balance_volume=1000, short_open_interest_balance_volume=400))
    return pd.DataFrame(rows)


def _txo_frame(no_call_idx=(2,)):
    rows = []
    for i, d in enumerate(_LD):
        for cp, lo, sh in (("買權", 300 + i, 100), ("賣權", 200 + 7 * i, 150)):
            if cp == "買權" and i in no_call_idx:
                continue
            rows.append(dict(date=d.isoformat(), call_put=cp, institutional_investors="外資及陸資",
                             long_open_interest_balance_volume=lo, short_open_interest_balance_volume=sh,
                             long_open_interest_balance_amount=10.0 * lo,
                             short_open_interest_balance_amount=5.0 * sh))
    return pd.DataFrame(rows)


class _Probe:
    status_code = 200


class _Sess:
    def get(self, *a, **k):
        return _Probe()


def _li_patch(mod, mp, tmp_path, *, taifex, pcr_taifex=None, pcr_raises=False):
    import shared.cache_layer as CL

    def _fm(ds, did, s, e, tok=""):
        if ds == "TaiwanFuturesInstitutionalInvestors":
            return _fut_frame()
        if ds == "TaiwanOptionInstitutionalInvestors":
            return _txo_frame()
        return pd.DataFrame()

    def _no_taifex():
        raise RuntimeError("offline")

    def _pcr(s, e):
        if pcr_raises:
            raise RuntimeError("pcr boom")
        return dict(pcr_taifex or {})

    mp.setattr(mod, "finmind_get", _fm)
    mp.setattr(mod, "_twse_margin_day", lambda d: {})
    mp.setattr(mod, "twse_volume", lambda m: {})
    mp.setattr(mod, "twse_volume_daily", lambda d: None)
    mp.setattr(mod, "_bps", (lambda: _Sess()) if taifex else _no_taifex)
    mp.setattr(mod, "taifex_pcr", _pcr)
    mp.setattr(mod, "taifex_large_trader", lambda d: None)
    mp.setattr(mod, "taifex_mtx_data", lambda d: None)
    mp.setattr(mod, "taifex_post", lambda *a, **k: "")
    mp.setattr(mod.time, "sleep", lambda s: None)
    mp.setattr(CL, "_PKL_DIR", str(tmp_path))


#: case → (taifex 可達, taifex_pcr 回傳, taifex_pcr 拋例外)
_LI_CASES = {
    "taifex-unreachable": (False, None, False),
    "taifex-mixed": (True, {_LDK[1]: 88.8, _LDK[2]: 133.3, _LDK[3]: 101.0, "20000103": 99.0}, False),
    "taifex-pcr-raises": (True, None, True),
    "taifex-empty": (True, {}, False),
}


def _run_li(mod, mp, tmp_path, case, token):
    taifex, pcr, boom = _LI_CASES[case]
    _li_patch(mod, mp, tmp_path, taifex=taifex, pcr_taifex=pcr, pcr_raises=boom)
    return mod.build_leading_fast(days=7, token=token)


def _pcr_src_problems(df, case) -> list[str]:
    """`_pcr_src` 的契約檢查（不變式＋每天標的來源）。回問題清單（空＝合規）。"""
    import src.data.macro.leading_indicators as LI
    probs = []
    if LI.PCR_SRC_COL not in df.columns:
        return [f"缺 {LI.PCR_SRC_COL} 欄"]
    if list(df.columns)[-3:] != [LI.PCR_SRC_COL, "source", "fetched_at"]:
        probs.append(f"欄序：{list(df.columns)[-3:]}")
    _, pcr_t, boom = _LI_CASES[case]
    taifex_days = set() if (boom or not _LI_CASES[case][0]) else set(pcr_t or {})
    for _, r in df.iterrows():
        v, s = r["選PCR"], r[LI.PCR_SRC_COL]
        if pd.isna(v) != pd.isna(s):          # pandas 3：object/str 欄的 None 會變 NaN ⇒ 一律以「缺」比
            probs.append(f"不變式破：{r['_date']} 選PCR={v!r} _pcr_src={s!r}")
            continue
        if pd.isna(s):
            continue
        want = LI.PCR_SRC_TAIFEX if r["_date"] in taifex_days else LI.PCR_SRC_FINMIND_EST
        if s != want:
            probs.append(f"{r['_date']} 標 {s!r}，應為 {want!r}")
    return probs


class TestPcrSource:
    def test_constants(self):
        import src.data.macro.leading_indicators as LI
        assert LI.PCR_SRC_COL == "_pcr_src"
        assert (LI.PCR_SRC_TAIFEX, LI.PCR_SRC_FINMIND_EST) == ("TAIFEX", "FinMind-TXO-inst-est")
        assert dict(LI.PCR_SRC_KIND) == {"TAIFEX": "official", "FinMind-TXO-inst-est": "proxy_estimate"}
        with pytest.raises(TypeError):
            LI.PCR_SRC_KIND["x"] = "y"                     # 唯讀
        assert LI.LI_VERSION == c1_pre_module(_LI).LI_VERSION == "v8-finmind-20260323"

    @pytest.mark.parametrize("case", sorted(_LI_CASES))
    def test_invariant_and_labels(self, case, monkeypatch, tmp_path):
        import src.data.macro.leading_indicators as LI
        df = _run_li(LI, monkeypatch, tmp_path, case, f"c1-inv-{next(_uid)}")
        assert not df.empty and set(_LDK) <= set(df["_date"])
        assert _pcr_src_problems(df, case) == []
        if case == "taifex-mixed":   # 至少一天 FinMind 沒有值（callV=0）而 TAIFEX 補上 ⇒ 那天標 TAIFEX
            row = df.set_index("_date").loc[_LDK[2]]
            assert row["選PCR"] == 133.3 and row[LI.PCR_SRC_COL] == LI.PCR_SRC_TAIFEX

    @pytest.mark.parametrize("case", sorted(_LI_CASES))
    def test_before_after_identical(self, case, monkeypatch, tmp_path, capsys):
        """C1 前（還原體）vs C1 後：去掉 `_pcr_src`、`fetched_at` 後逐格相同；stdout 逐字相同；快取內容同理。"""
        import src.data.macro.leading_indicators as LI
        pre = c1_pre_module(_LI)
        a_dir, b_dir = tmp_path / "new", tmp_path / "pre"
        a_dir.mkdir(); b_dir.mkdir()
        tok = f"c1-eq-{next(_uid)}"
        capsys.readouterr()
        new = _run_li(LI, monkeypatch, a_dir, case, tok)
        out_new = capsys.readouterr().out
        old = _run_li(pre, monkeypatch, b_dir, case, tok)
        out_old = capsys.readouterr().out
        assert LI.PCR_SRC_COL not in old.columns
        pd.testing.assert_frame_equal(new.drop(columns=[LI.PCR_SRC_COL, "fetched_at"]),
                                      old.drop(columns=["fetched_at"]))
        assert out_new == out_old
        _downstream_identical(new, old)
        # 快取：兩邊寫不寫一致；寫了則去掉 `_pcr_src` 後相同（快取鍵沿用 → 檔名相同）
        pk_new, pk_old = sorted(os.listdir(a_dir)), sorted(os.listdir(b_dir))
        assert [f for f in pk_new if f.endswith(".pkl")] == [f for f in pk_old if f.endswith(".pkl")]
        for f in (f for f in pk_new if f.endswith(".pkl")):
            with open(a_dir / f, "rb") as fa, open(b_dir / f, "rb") as fb:
                ca, cb = pickle.load(fa), pickle.load(fb)
            pd.testing.assert_frame_equal(ca.drop(columns=[LI.PCR_SRC_COL]), cb)

    def test_old_pickle_returned_as_is(self, monkeypatch, tmp_path):
        """修前寫的 pickle（沒有 `_pcr_src`）照原樣回傳（不回填、不補欄），新舊模組結果相同。"""
        import src.data.macro.leading_indicators as LI
        import hashlib as _h
        old_df = pd.DataFrame([{"_date": _LDK[-1], "選PCR": 99.9, "外資大小": 1, "source": "x"}])
        tok = f"c1-pk-{next(_uid)}"
        outs = []
        for mod in (LI, c1_pre_module(_LI)):
            d = tmp_path / f"m{next(_uid)}"
            d.mkdir()
            with open(d / (_h.md5(f"lead_fast_7_{tok}".encode()).hexdigest() + ".pkl"), "wb") as f:
                pickle.dump(old_df, f)
            _li_patch(mod, monkeypatch, d, taifex=False)
            outs.append(mod.build_leading_fast(days=7, token=tok))
        pd.testing.assert_frame_equal(outs[0], outs[1])
        pd.testing.assert_frame_equal(outs[0], old_df)
        assert LI.PCR_SRC_COL not in outs[0].columns

    def test_full_path_build_leading_indicators(self, monkeypatch, tmp_path):
        """另一路徑 `build_leading_indicators` 同 schema：TAIFEX 有值 ⇒ 'TAIFEX'，無值 ⇒ None；其餘欄與 C1 前相同。"""
        import src.data.macro.leading_indicators as LI
        outs = []
        for mod in (LI, c1_pre_module(_LI)):
            monkeypatch.setattr(mod, "twse_volume", lambda m: {k: 1000.0 for k in _LDK})
            monkeypatch.setattr(mod, "finmind_fut_oi", lambda s, e, t: {})
            monkeypatch.setattr(mod, "taifex_pcr", lambda s, e: {_LDK[0]: 90.0, _LDK[3]: 110.0})
            for nm in ("twse_institutional_day", "taifex_large_trader", "taifex_calls_puts_day",
                       "taifex_mtx_data"):
                monkeypatch.setattr(mod, nm, lambda d: {} if nm != "taifex_calls_puts_day" else None)
            monkeypatch.setattr(mod.time, "sleep", lambda s: None)
            outs.append(mod.build_leading_indicators(_LD[0], _LD[-1]))
        new, old = outs
        got = dict(zip(new["_date"], new[LI.PCR_SRC_COL]))
        assert {k: (None if pd.isna(v) else v) for k, v in got.items()} == {
            k: ("TAIFEX" if k in (_LDK[0], _LDK[3]) else None) for k in _LDK}
        assert (new["選PCR"].isna() == new[LI.PCR_SRC_COL].isna()).all()
        pd.testing.assert_frame_equal(new.drop(columns=[LI.PCR_SRC_COL, "fetched_at"]),
                                      old.drop(columns=["fetched_at"]))

    @pytest.mark.parametrize("mutation", ["no-finmind-tag", "no-taifex-tag", "no-row-col", "unguarded"])
    def test_mutations_turn_red(self, mutation, monkeypatch, tmp_path):
        """突變：拔掉任一處新增邏輯 ⇒ `_pcr_src_problems` 抓得到（現行碼為空，見上）。"""
        swaps = {
            "no-finmind-tag": [("                pcr_src[dk] = PCR_SRC_FINMIND_EST\n", "")],
            "no-taifex-tag": [("            pcr_src.update(dict.fromkeys(pcr_taifex, PCR_SRC_TAIFEX))"
                               "   # C1:同一批鍵改標 TAIFEX\n", "")],
            "no-row-col": [("            PCR_SRC_COL:  (pcr_src.get(d) if pcr_dict.get(d) is not None else None),\n",
                            "")],
            # 去掉「選PCR 為 None ⇒ None」的保護，並讓 TAIFEX 回一個 None 值（只有 mock 會發生）
            "unguarded": [("            PCR_SRC_COL:  (pcr_src.get(d) if pcr_dict.get(d) is not None else None),\n",
                           "            PCR_SRC_COL:  pcr_src.get(d),\n")],
        }[mutation]
        mut = c1_mutant_module(_LI, swaps, f"pcr_{mutation.replace('-', '_')}_{next(_uid)}")
        case = "taifex-mixed"
        if mutation == "unguarded":
            _li_patch(mut, monkeypatch, tmp_path, taifex=True, pcr_taifex={_LDK[1]: None})
            df = mut.build_leading_fast(days=7, token=f"c1-mut-{next(_uid)}")
            assert any("不變式破" in p for p in _pcr_src_problems(df, "taifex-empty"))
            return
        df = _run_li(mut, monkeypatch, tmp_path, case, f"c1-mut-{next(_uid)}")
        assert _pcr_src_problems(df, case) != []


def _downstream_identical(new_li, old_li):
    """同一份 session（只差 li_latest 有無 `_pcr_src`）餵下游 → 完全相等。"""
    from src.compute.macro import calc_traffic_light
    from src.compute.macro.dated_inputs import extract_leading
    from src.compute.macro.macro_helpers import compute_five_bucket_summary
    from src.services.macro_engine_inputs import build_engine_inputs
    from src.services.macro_state_locker import calculate_system_state

    assert extract_leading(new_li) == extract_leading(old_li)
    now = datetime.combine(dt.date.today(), dt.time(18, 0), tzinfo=_TW)
    kw = dict(macro_info={"vix": {"current": 17.3, "date": _LD[-1].isoformat()}},
              bias_info={"bias_240": 5.0, "as_of": _LD[-1].isoformat()},
              m1b_m2_info={}, mkt_info={"index_below_ma5": False, "index_as_of": _LD[-1].isoformat()},
              pmi_history=None, now=now, calendar=None)
    b_new = build_engine_inputs(li_latest=new_li, **kw)
    b_old = build_engine_inputs(li_latest=old_li, **kw)
    assert b_new.macro_numbers == b_old.macro_numbers
    assert b_new.not_evaluated == b_old.not_evaluated
    assert dict(b_new.input_asof) == dict(b_old.input_asof)
    assert dict(b_new.assessed) == dict(b_old.assessed)
    assert (calculate_system_state(dict(b_new.macro_numbers), include_veto_flags=True)
            == calculate_system_state(dict(b_old.macro_numbers), include_veto_flags=True))
    mkt = {"score": 3, "regime": "neutral", "max_score": 4.0}
    jq = {"is_proxy": False, "avg": 60}
    cl = {"intl": {}, "tw": {}, "tech": {}, "inst": {"外資及陸資": {"net": 12.3}},
          "inst_date": None, "margin": None, "adl": None}
    assert calc_traffic_light(mkt, jq, cl, new_li) == calc_traffic_light(mkt, jq, cl, old_li)
    rd_new, rd_old = {}, {}
    s_new = compute_five_bucket_summary(mkt_info=mkt, cl_data=cl, li_latest=new_li, jingqi_info=jq,
                                        readiness_out=rd_new)
    s_old = compute_five_bucket_summary(mkt_info=mkt, cl_data=cl, li_latest=old_li, jingqi_info=jq,
                                        readiness_out=rd_old)
    assert s_new == s_old
    assert rd_new == rd_old            # readiness 側車（實測不含 DataFrame 參照）逐鍵相等


# ══════════════════════════════════════════════════════════════════════════
# 4. DH-C1-FWD-LEG-ASOF
# ══════════════════════════════════════════════════════════════════════════
_LEG = ("score_index_as_of", "inst_as_of", "adl_as_of", "li_as_of")


def _tl(**over):
    base = {"icon": "🔴", "label": "空頭防禦｜降低部位", "effective_regime": "bear",
            "regime_source": "health_defense", "defense": True, "health": 40.2, "health_partial": False,
            "score": 2.0, "max_score": 5.0, "jqavg": 49.3, "conf": 100,
            "conf_groups": {"yfinance_twii": True}, "missing_sources": ["x", "y"]}
    base.update(over)
    return base


class TestLedgerSchema:
    def test_schema_version_and_columns(self):
        import shared.macro_forward_test_schema as S
        pre = c1_pre_module(_SCHEMA)
        assert S.MACRO_FWD_TEST_SCHEMA_VERSION == pre.MACRO_FWD_TEST_SCHEMA_VERSION == 3
        assert S.MACRO_FWD_TEST_LEG_AS_OF_COLUMNS == _LEG
        assert S.MACRO_FWD_TEST_HEADERS == pre.MACRO_FWD_TEST_HEADERS + _LEG

    def test_ruleset_hash_unchanged(self):
        from src.compute.macro.macro_forward_test import compute_ruleset_hash
        pre = c1_pre_module(_MFT)
        assert pre.MACRO_FWD_TEST_HEADERS == c1_pre_module(_SCHEMA).MACRO_FWD_TEST_HEADERS   # 真 C1 前 schema
        assert compute_ruleset_hash() == pre.compute_ruleset_hash()


_ROW_KW = [
    dict(date="2026-10-22", captured_at="2026-10-23T17:40:00+08:00"),
    dict(date="2026-10-22", captured_at="c", twii_close=21000.5, inputs_as_of="2026-10-22",
         git_sha="abc", ruleset_hash="h", date_source="live_as_of"),
    dict(date="2026-10-22", captured_at="c", inputs_as_of="2026-10-21", date_source="backfill_from_captured_at"),
]


def _row_problems(row, pre_row, leg) -> list[str]:
    probs = []
    if list(row)[:len(pre_row)] != list(pre_row):
        probs.append("舊鍵順序不同")
    if {k: row.get(k) for k in pre_row} != pre_row:
        probs.append("舊鍵值不同")
    if tuple(row)[len(pre_row):] != _LEG:
        probs.append(f"新鍵：{tuple(row)[len(pre_row):]}")
    for k in _LEG:
        if row.get(k) != (leg or {}).get(k):
            probs.append(f"{k}={row.get(k)!r}")
    return probs


class TestBuildSignalRow:
    @pytest.mark.parametrize("kw", _ROW_KW)
    @pytest.mark.parametrize("tl", [_tl(), _tl(health=None, jqavg=None, missing_sources=[], conf=0)])
    @pytest.mark.parametrize("leg", [None, {}, {"inst_as_of": "2026-10-22"},
                                     dict(zip(_LEG, ("2026-10-22", "2026-10-22", "2026-10-21", "2026-10-22")))])
    def test_old_keys_unchanged_new_keys_exactly_four(self, kw, tl, leg):
        from src.compute.macro.macro_forward_test import build_signal_row
        pre_row = c1_pre_module(_MFT).build_signal_row(copy.deepcopy(tl), **kw)
        extra = {} if leg is None else {"leg_as_of": leg}
        row = build_signal_row(copy.deepcopy(tl), **kw, **extra)
        assert _row_problems(row, pre_row, leg) == []

    def test_unknown_leg_key_rejected(self):
        from src.compute.macro.macro_forward_test import build_signal_row
        with pytest.raises(ValueError, match="leg_as_of"):
            build_signal_row(_tl(), date="2026-10-22", captured_at="c", leg_as_of={"inputs_as_of": "x"})

    def test_live_date_check_unchanged(self):
        from src.compute.macro.macro_forward_test import build_signal_row
        for f in (build_signal_row, c1_pre_module(_MFT).build_signal_row):
            with pytest.raises(ValueError, match="inputs_as_of"):
                f(_tl(), date="2026-10-22", captured_at="c", inputs_as_of="2026-10-21",
                  date_source="live_as_of")

    def test_mutation_dropping_four_columns_turns_red(self):
        """突變：拔掉 build_signal_row 的四欄迴圈 ⇒ `_row_problems` 抓得到。"""
        mut = c1_mutant_module(_MFT, [(
            "    for _k in MACRO_FWD_TEST_LEG_AS_OF_COLUMNS:\n"
            "        row[_k] = (str(_leg[_k]) if _leg.get(_k) else None)\n", "")], f"mft_{next(_uid)}")
        leg = dict(zip(_LEG, ("2026-10-22",) * 4))
        kw = _ROW_KW[0]
        pre_row = c1_pre_module(_MFT).build_signal_row(_tl(), **kw)
        assert _row_problems(mut.build_signal_row(_tl(), **kw, leg_as_of=leg), pre_row, leg) != []


class TestLegAsOfFromInputs:
    @staticmethod
    def _f(**kw):
        from src.compute.macro.macro_forward_test import leg_as_of_from_inputs
        base = dict(mkt_info={"index_as_of": "2026-10-23"}, inst={"外資": {"net": 1.0}},
                    inst_date="20261023",
                    df_adl=pd.DataFrame({"date": pd.to_datetime(["2026-10-21", "2026-10-22"]), "ad_ratio": [50, 51]}),
                    li_latest=pd.DataFrame({"_date": ["20261022", "20261023"], "選PCR": [1.0, 2.0]}))
        base.update(kw)
        return leg_as_of_from_inputs(**base)

    def test_normal(self):
        assert self._f() == {"score_index_as_of": "2026-10-23", "inst_as_of": "2026-10-23",
                             "adl_as_of": "2026-10-22", "li_as_of": "2026-10-23"}

    @pytest.mark.parametrize("inst", [{}, None])
    def test_inst_empty_means_no_date(self, inst):
        """`fetch_institutional` 失敗回的是請求日 ⇒ inst 空時不記 inst_as_of。"""
        assert self._f(inst=inst)["inst_as_of"] is None

    @pytest.mark.parametrize("over, key", [
        (dict(mkt_info=None), "score_index_as_of"), (dict(mkt_info={"index_as_of": "2026-10-1"}), "score_index_as_of"),
        (dict(df_adl=None), "adl_as_of"), (dict(df_adl=pd.DataFrame()), "adl_as_of"),
        (dict(df_adl=pd.DataFrame({"x": [1]})), "adl_as_of"), (dict(li_latest=None), "li_as_of"),
        (dict(li_latest=pd.DataFrame({"x": [1]})), "li_as_of"), (dict(li_latest=42), "li_as_of"),
        (dict(inst_date="bogus"), "inst_as_of"),
    ])
    def test_each_leg_fails_alone(self, over, key, capsys):
        out = self._f(**over)
        assert out[key] is None
        normal = self._f()
        assert {k: v for k, v in out.items() if k != key} == {k: v for k, v in normal.items() if k != key}

    def test_does_not_mutate_inputs(self):
        args = dict(mkt_info={"index_as_of": "2026-10-23"}, inst={"外資": {"net": 1.0}}, inst_date="20261023",
                    df_adl=pd.DataFrame({"date": pd.to_datetime(["2026-10-22"])}),
                    li_latest=pd.DataFrame({"_date": ["20261023"]}))
        snap = copy.deepcopy(args)
        self._f(**args)
        assert args["mkt_info"] == snap["mkt_info"] and args["inst"] == snap["inst"]
        pd.testing.assert_frame_equal(args["df_adl"], snap["df_adl"])
        pd.testing.assert_frame_equal(args["li_latest"], snap["li_latest"])


# ── cron main()：隔離所有真實 I/O（同 tests/test_macro_fwd_test_c12.py::_isolate）────
def _cron_isolate(monkeypatch, tmp_path, *, mkt_info):
    import streamlit as st
    import scripts.update_macro_forward_test as S
    import src.compute.macro as CM
    import src.data.macro.macro_fwd_test_store as store
    import src.services.jingqi_calc as JQ
    import src.services.market_assessment_apply as MA
    twii = pd.DataFrame({"close": [100.0, 101.0]}, index=pd.to_datetime(["2026-08-17", "2026-08-18"]))
    bundle = {"tw_raw": {"台股加權指數": twii}, "inst": {"外資": {"net": 1.0}}, "inst_date": "20260818",
              "df_adl_raw": pd.DataFrame({"date": pd.to_datetime(["2026-08-17"]), "is_proxy": [True]}),
              "df_li_a": pd.DataFrame({"_date": ["20260818"]})}
    monkeypatch.setattr(S, "_fetch_live_bundle", lambda *a, **k: bundle)
    monkeypatch.setattr(S, "_git_sha", lambda: "test0000")
    monkeypatch.setattr(S, "_now_tw", lambda: datetime.fromisoformat("2026-08-18T17:40:00+08:00"))
    monkeypatch.setattr(MA, "compute_and_apply_market_assessment",
                        lambda **k: st.session_state.__setitem__("mkt_info", dict(mkt_info)))
    monkeypatch.setattr(JQ, "compute_and_store_jingqi", lambda *a, **k: None)
    monkeypatch.setattr(CM, "calc_traffic_light", lambda *a, **k: _tl())
    monkeypatch.setattr(store, "MACRO_FWD_TEST_PATH", tmp_path / "signals.parquet")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    return S, store


@pytest.fixture
def _clean_session():
    import streamlit as st
    saved = {k: st.session_state.get(k) for k in ("mkt_info", "cl_data", "jingqi_info")}
    yield
    for k, v in saved.items():
        if v is None:
            st.session_state.pop(k, None) if hasattr(st.session_state, "pop") else None
        else:
            st.session_state[k] = v


class TestCronMain:
    def test_writes_four_leg_dates(self, monkeypatch, tmp_path, _clean_session):
        S, store = _cron_isolate(monkeypatch, tmp_path, mkt_info={"index_as_of": "2026-08-18"})
        assert S.main([]) == 0
        (row,) = store.load_signals()
        assert {k: row[k] for k in _LEG} == {"score_index_as_of": "2026-08-18", "inst_as_of": "2026-08-18",
                                             "adl_as_of": "2026-08-17", "li_as_of": "2026-08-18"}
        assert row["date"] == row["inputs_as_of"] == "2026-08-18"     # date／inputs_as_of 產生方式不變

    def test_leg_function_raising_still_writes_row(self, monkeypatch, tmp_path, _clean_session, capsys):
        import src.compute.macro.macro_forward_test as MFT
        S, store = _cron_isolate(monkeypatch, tmp_path / "a", mkt_info={"index_as_of": "2026-08-18"})
        (tmp_path / "a").mkdir()
        assert S.main([]) == 0
        (normal,) = store.load_signals()

        def _boom(**k):
            raise RuntimeError("leg boom")
        monkeypatch.setattr(MFT, "leg_as_of_from_inputs", _boom)
        monkeypatch.setattr(store, "MACRO_FWD_TEST_PATH", tmp_path / "b" / "signals.parquet")
        assert S.main([]) == 0
        (row,) = store.load_signals()
        assert all(row[k] is None for k in _LEG)
        assert {k: v for k, v in row.items() if k not in _LEG} == {k: v for k, v in normal.items() if k not in _LEG}
        assert "各腿資料日取不到" in capsys.readouterr().out


class TestCommittedLedgerAppend:
    def test_old_rows_unchanged_after_append(self, tmp_path):
        """已提交帳本複製到 tmp：C1 後 append 一列 vs C1 前 append 同一列（去掉四欄）⇒ 舊欄逐格相同；舊列四欄 None。"""
        pytest.importorskip("pyarrow")
        import src.data.macro.macro_fwd_test_store as store
        from src.compute.macro.macro_forward_test import build_signal_row
        src_pq = REPO / "data_cache" / "macro_forward_test" / "signals.parquet"
        orig = pd.read_parquet(src_pq)
        pre_schema = c1_pre_module(_SCHEMA)
        pre_store = _exec_as_module("src/data/macro/macro_fwd_test_store.py",
                                    (REPO / "src/data/macro/macro_fwd_test_store.py").read_text(encoding="utf-8"),
                                    f"_c1_pre_store_{next(_uid)}",
                                    swap={"shared.macro_forward_test_schema": pre_schema})
        assert pre_store.MACRO_FWD_TEST_HEADERS == pre_schema.MACRO_FWD_TEST_HEADERS
        leg = dict(zip(_LEG, ("2099-01-01", None, "2098-12-31", "2099-01-01")))
        kw = dict(date="2099-01-01", captured_at="2099-01-01T17:40:00+08:00", twii_close=1.0,
                  inputs_as_of="2099-01-01", git_sha="t", ruleset_hash="h", date_source="live_as_of")
        row_new = build_signal_row(_tl(), **kw, leg_as_of=leg)
        row_old = c1_pre_module(_MFT).build_signal_row(_tl(), **kw)
        p_new, p_old = tmp_path / "new.parquet", tmp_path / "old.parquet"
        shutil.copyfile(src_pq, p_new)
        shutil.copyfile(src_pq, p_old)
        assert store.append_signals([row_new], path=p_new) == 1
        assert pre_store.append_signals([row_old], path=p_old) == 1
        a, b = pd.read_parquet(p_new), pd.read_parquet(p_old)
        assert list(a.columns) == list(b.columns) + list(_LEG)
        pd.testing.assert_frame_equal(a[list(b.columns)], b)
        old_part = a[a["date"].isin(set(orig["date"].astype(str)))]
        assert len(old_part) == len(orig) and old_part[list(_LEG)].isna().all().all()
        new_part = a[a["date"] == "2099-01-01"].iloc[0]
        assert [new_part[k] if new_part[k] is not None and not pd.isna(new_part[k]) else None
                for k in _LEG] == [leg[k] for k in _LEG]
        # 已提交的檔案本身一個位元組都沒動
        assert pd.read_parquet(src_pq).equals(orig)


# ══════════════════════════════════════════════════════════════════════════
# 5. 零讀者守衛：新欄名／常數只出現在生產者模組、schema 檔與 tests
# ══════════════════════════════════════════════════════════════════════════
_NEW_NAMES = ("_pcr_src", "PCR_SRC_COL", "PCR_SRC_KIND", "PCR_SRC_TAIFEX", "PCR_SRC_FINMIND_EST") + _LEG
_ALLOWED = {_LI, _SCHEMA, _MFT}


def test_new_fields_have_no_readers():
    pat = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(map(re.escape, _NEW_NAMES)) + r")(?![A-Za-z0-9_])")
    hits = {}
    files = [REPO / "app.py"] + [p for d in ("src", "shared", "scripts") for p in (REPO / d).rglob("*.py")]
    for p in files:
        rel = p.relative_to(REPO).as_posix()
        if "__pycache__" in rel:
            continue
        found = set(pat.findall(p.read_text(encoding="utf-8")))
        if found:
            hits[rel] = found
    assert set(hits) <= _ALLOWED, {k: v for k, v in hits.items() if k not in _ALLOWED}
    assert "_pcr_src" in hits.get(_LI, set())
    assert set(_LEG) <= hits.get(_SCHEMA, set())


def test_no_judgement_reads_leg_dates_in_mft():
    """macro_forward_test 內四欄名只出現在 schema 常數的引用（取值／寫入），不出現在 if／比較式裡。"""
    import ast
    tree = ast.parse((REPO / _MFT).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.Compare, ast.IfExp, ast.While)):
            seg = ast.dump(node.test if hasattr(node, "test") else node)
            assert not any(f"'{k}'" in seg for k in _LEG), seg[:200]
