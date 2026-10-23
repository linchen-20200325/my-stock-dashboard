"""DEC-074 B／DEC-075 批 A＋批 1'（客戶 2026-10-23）—— 舊批次「還原鏈」的最新一節。

本 repo 的慣例：每個批次登記自己的 `(新寫法, 舊寫法)` 還原組，舊批次的回歸測試先把「更新的批次」
換回去、再換回自己的那一批，最後逐位比對各自的基底 sha256（例：`tests/test_vn1_store_poc.py::
vn1store_revert_for`、`tests/test_batch_z62.py::z62_revert_for`）。本批改了其中幾條鏈管的檔
（`macro_state_locker`／`page_today`／`market_strategy`／`market_assessment_apply`／`macro_helpers`／
`macro_fetch_orchestrator`…），故在鏈頭往前接一節：`dec074_revert_for` 把本批改動換回基底
`b9ed892d`（main，本批開工前）的寫法。

⚠️ **只套一次（idempotent）**：本批改到的檔同時被好幾條鏈管（例：z36 同時串 z62 與 z65→…→vn1store），
同一份程式碼可能經過兩個掛點。判定（整檔一起看，不逐組）：
  · 每一組的 `新寫法` 都恰好出現一次 ⇒ 換回；
  · 每一組的 `新寫法` 都 0 次 ⇒ 已被前一個掛點換回，原樣返回；
  · 其餘（有 1 有 0、或出現多次）⇒ AssertionError（錨點漂移，必須重產還原組）。
「全 0 卻其實是漂移」的情形由 `test_dec074_revert_is_exact_base_source`（對現行檔必須全 1 且逐位還原）擋下。

還原組由 `difflib` 對 `git show b9ed892d:<檔>` 與工作樹逐 hunk 產生（最小上下文），
並由 `test_dec074_revert_is_exact_base_source` 守：還原後逐位等於基底 sha256。
基底 sha 寫死以免測試依賴 git。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DEC074_BASE_SHA = {'shared/macro_forward_test_schema.py': '2c50db57f68367b2d4580e8c6e292d377f5ef99c59fd958082c755ed55b0c93c',
 'shared/macro_provenance.py': 'b780bb3cd655ce0c7d9ccbfb6ebcbc1051ca1f35bff133f486f720d895329c83',
 'shared/regime_arbiter.py': 'a5a7a81386c4e5a36efac69483eba665edbabbd611f0475b6fa398ad9cc3b4fb',
 'shared/signal_thresholds.py': '9f629902b72a584cefe6956ca72b50e389d7d695c97c825c0d415831275c3656',
 'src/compute/macro/macro_forward_test.py': 'befdcd0b35f680cd2f863bb1f47273208e1e9213273cf2c0f7421f417b3410de',
 'src/compute/macro/macro_helpers.py': '10e42e7d4773a3944aaf1484ae87e456c5b305f0fe36fc7f773e0dc7ee139767',
 'src/services/jingqi_calc.py': '9443980c4b15de033d8645e2d77d3990c7782913c1881a145f218b6212a1bca9',
 'src/services/macro_refresh_service.py': 'f1606dec90304bf3895caa14e5bd4b73387042c962d6418b96a0a8b50474b955',
 'src/services/macro_state_locker.py': 'f43e7c20b9c03f1c03a3452308728309d350f4015b948ab40c1df7caf02dc1a3',
 'src/services/market_assessment_apply.py': 'b9ed911a03531dc9a6dddb33f405d79bac92f9cefe8f3fab53cd4b5d64128ed7',
 'src/services/market_strategy.py': 'ade4b3a9b729aba1589669dd0e85f9c10b4ee0a8d1bcbbe6820ba25265e97c89',
 'src/services/reconcile_service.py': 'd4390625de6c44a1eef7b14654faf4df9cd13dd526dd07908b8aaa52e3a4a3c1',
 'src/ui/tabs/macro/handlers.py': 'e23c5556742986c0b6ac5c7fe3e50c5d6ab3ad0514daa0258c4996024be4d9c1',
 'src/ui/tabs/macro/section_short.py': '1cb052c72acc6650b0bcff60ebbe65e8be4395950712e5c6d39ddf891c2a79d1',
 'src/ui/tabs/tab_macro_v2.py': 'cb34f1720781f5f7d55e484becebcedfd65adafc4eec0454773cafa0bf9f1617',
 'src/ui/views/page_today.py': '672697ff9437a9c624840d35e6098a6d8484417ed6a9be462f7d89fcc4be37ac'}

DEC074_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'shared/macro_forward_test_schema.py': (('#: (1→2),不是規則改版(2026-10-15 總管裁定:hash 演算法不改,在此註明)。\n'
                                          '#: 📌 v3（2026-10-23，DEC-074 B／DEC-075 批 A，有意識的 bump）：未改欄位，但 '
                                          '`health`／`jqavg`／\n'
                                          '#: `regime_source` 三欄的**語意**改變 —— 市場廣度只有代理（估算）家數時 '
                                          '`jqavg=None`、`health=None`、\n'
                                          '#: '
                                          "`regime_source='unevaluated:breadth_unavailable'`（原為「只剩大盤分重新歸一」的分數）。屬「改語意」\n"
                                          '#: ⇒ +1；`compute_ruleset_hash` 同時加入 `breadth_proxy_scoring` '
                                          '旗標，hash 必變。\n'
                                          '#: ⚠️ v2 列與 v3 列**不可混比**（健康分口徑不同）；歷史列的 `schema_version` '
                                          '維持寫入當時的值。\n'
                                          '#: ⚠️ 預告（未授權、另批）：計畫第 4 節 `DH-MACRO-FWD-ASOF`（per-leg as_of '
                                          '加欄）若日後實作會再 bump 一次。\n'
                                          'MACRO_FWD_TEST_SCHEMA_VERSION: int = 3\n'
                                          '\n',
                                          '#: (1→2),不是規則改版(2026-10-15 總管裁定:hash 演算法不改,在此註明)。\n'
                                          'MACRO_FWD_TEST_SCHEMA_VERSION: int = 2\n'
                                          '\n'),),
 'shared/macro_provenance.py': (('§8.2 分層：L0 Infra，零 import（含 stdlib 亦不需要），可被任何層引用。\n'
                                 '（DEC-074 B 起 `jingqi_for_scoring` 函式內 lazy import 同層 L0 '
                                 '`shared.signal_thresholds` 的計分開關 —— L0→L0，非上行。）\n'
                                 '"""\n',
                                 '§8.2 分層：L0 Infra，零 import（含 stdlib 亦不需要），可被任何層引用。\n"""\n'),
                                ('    return info\n'
                                 '\n'
                                 '\n'
                                 '# ══════════════════════════════════════════════════════════════════════\n'
                                 '# 市場廣度（漲跌家數／旌旗）代理判定 —— DEC-074 B（客戶 2026-10-23）\n'
                                 '# ══════════════════════════════════════════════════════════════════════\n'
                                 '# 鏡像上方 M1B 三支（`is_m1b_m2_proxy` / `m1b_m2_proxy_badge` / '
                                 '`m1b_m2_for_scoring`），\n'
                                 '# 不發明第二種機制（DEC-037 先例）。計分開關在 L0\n'
                                 '# `shared.signal_thresholds.BREADTH_PROXY_SCORING_ENABLED`（現為 False）。\n'
                                 '#\n'
                                 '# 為什麼 `jingqi_info` 只認**明確布林旗標**、不做 source 字串比對：\n'
                                 '# producer（`src/services/jingqi_calc.compute_and_store_jingqi`、舊 UI '
                                 '`section_short` 的\n'
                                 '# TWSE 單日頂替）自本批起一律寫 `is_proxy`；沒有旗標的 dict（測試 fixture、`section_inputs`\n'
                                 "# 由 warroom 合成的 `{'avg': ...}`）沿用既有語意 = 真值（M1B 同一個分寸：拿不到旗標時\n"
                                 '# 「不宣稱它是代理值」）。⚠️ 上游 **DataFrame**（`fetch_adl` 的回傳）則相反 —— 缺 `is_proxy`\n'
                                 '# 欄**一律視同代理**（fail-safe）：那是原始序列、本 repo 所有已知產出都帶此欄，缺欄＝\n'
                                 '# 契約漂移，不得因此把估算家數當真值計分（見 `adl_df_is_proxy`）。\n'
                                 '\n'
                                 '#: 代理廣度值貼在數字後面的短註記（顯示用；判燈／計分一律不讀）。\n'
                                 "BREADTH_PROXY_VALUE_NOTE: str = '（代理估算值，不計分）'\n"
                                 '\n'
                                 '#: 受本判定管轄的五桶燈 key（`shared.macro_buckets.BUCKET_DANGER_SPECS` 的 key）。\n'
                                 "BREADTH_LAMP_KEYS: frozenset = frozenset({'jingqi', 'adl'})\n"
                                 '\n'
                                 '\n'
                                 'def is_breadth_proxy(info: Optional[dict]) -> bool:\n'
                                 '    """`jingqi_info`（或五桶 readiness 側車的一筆 record）是不是代理（估算）廣度？\n'
                                 '\n'
                                 '    只認明確布林旗標 `is_proxy` / `is_proxy_tier` 為 True（見上方說明）。\n'
                                 '    `info` 為 None / 非 dict / 沒有旗標 → False。\n'
                                 '    """\n'
                                 '    if not isinstance(info, dict):\n'
                                 '        return False\n'
                                 '    return any(info.get(_k) is True for _k in _PROXY_FLAG_KEYS)\n'
                                 '\n'
                                 '\n'
                                 'def breadth_proxy_badge(info: Optional[dict]) -> str:\n'
                                 '    """代理廣度 → `BREADTH_PROXY_VALUE_NOTE`；否則 `\'\'`（非代理時串接後逐字元不變）。"""\n'
                                 "    return BREADTH_PROXY_VALUE_NOTE if is_breadth_proxy(info) else ''\n"
                                 '\n'
                                 '\n'
                                 'def jingqi_for_scoring(info: Optional[dict]) -> Optional[dict]:\n'
                                 '    """計分端取 `jingqi_info` 的唯一入口：代理廣度（且 L0 計分開關關閉）→ ``None``；否則原物件。\n'
                                 '\n'
                                 '    DEC-074 B：代理廣度**可以顯示**、**不得計分**。呼叫端把回傳當 `jingqi_info` 用 ——\n'
                                 '    代理時拿到 ``None``，走各自既有的「旌旗缺席」路徑；**但** `calc_traffic_light` 自本批起\n'
                                 '    「旌旗缺席 ⇒ 健康分 None（⬜ 未評估）」，不再只剩大盤分重新歸一（DEC-074「不得自行創造\n'
                                 '    新權重重新正規化」）。非代理時回**同一個物件**（不複製）⇒ 既有計分輸入逐位不變。\n'
                                 '    顯示端請照舊讀原始 `jingqi_info`（才看得到代理值與註記）。\n'
                                 '    """\n'
                                 '    from shared.signal_thresholds import BREADTH_PROXY_SCORING_ENABLED\n'
                                 '    if is_breadth_proxy(info) and not BREADTH_PROXY_SCORING_ENABLED:\n'
                                 '        return None\n'
                                 '    return info\n'
                                 '\n'
                                 '\n'
                                 'def adl_df_is_proxy(df) -> bool:\n'
                                 '    """`fetch_adl` 回傳的 DataFrame 末列是不是代理（估算）家數？**fail-safe：拿不準一律 True。**\n'
                                 '\n'
                                 '    - None / 空 → True（沒有可宣稱為真值的列；呼叫端本來就會走缺值路徑）\n'
                                 '    - 缺 `is_proxy` 欄 → True（契約漂移，不得把估算當真值計分）\n'
                                 '    - 末列 `is_proxy` 不是明確的 False（含 NaN / None / True）→ True\n'
                                 '\n'
                                 '    只看**末列**：`market_regime` 吃的是末列 `ad_ratio`；旌旗吃 `tail(5)` 的另見\n'
                                 '    `adl_rows_any_proxy`。純 duck typing，L0 不 import pandas。\n'
                                 '    """\n'
                                 '    return adl_rows_any_proxy(df, 1)\n'
                                 '\n'
                                 '\n'
                                 'def adl_rows_any_proxy(df, n: int) -> bool:\n'
                                 '    """`df` 的最後 `n` 列只要有一列不是明確 `is_proxy is False` → '
                                 'True（fail-safe，同上）。"""\n'
                                 '    try:\n'
                                 '        if df is None or len(df) == 0:\n'
                                 '            return True\n'
                                 "        if 'is_proxy' not in getattr(df, 'columns', ()):\n"
                                 '            return True\n'
                                 "        _tail = df['is_proxy'].tail(max(int(n), 1)).tolist()\n"
                                 '    except Exception:  # noqa: BLE001 — 讀不出旗標 = 拿不準 = '
                                 '代理（fail-safe，不吞成「真值」）\n'
                                 '        return True\n'
                                 '    # `tolist()` 已把 numpy bool 轉成 Python bool；NaN／None／字串都不是 `False` ⇒ '
                                 '代理。\n'
                                 '    return not all(_v is False for _v in _tail)\n',
                                 '    return info\n')),
 'shared/regime_arbiter.py': (('\n'
                               "SOURCE_UNEVALUATED_BREADTH: str = 'unevaluated:breadth_unavailable'\n"
                               '"""總經未評估 —— **原因是缺真實市場廣度**（DEC-074 B，客戶 2026-10-23）。**不是**一種市場判斷。\n'
                               '\n'
                               '與 `SOURCE_UNLOADED` 的差別（兩者 regime／燈號／`is_loaded` 完全相同，只差原因）：\n'
                               '`unloaded` ＝ 上游輸入缺失（重新抓取**可能**有用）；本值 ＝ 健康分的廣度腿只有代理（估算）\n'
                               '家數、依 DEC-074 不計分，**重新抓取不會改變**（`calc_traffic_light` 文案與新 UI 出口據此分流）。\n'
                               'DEC-075 D-1(a)：`macro_state_locker.get_macro_state` 見到 warroom '
                               '帶本值時，位階一併未評估，\n'
                               '⛔ 不退 `macro_state.json` 規則引擎位階（`SOURCE_FILE_RULE_ENGINE`）。"""\n'
                               '\n'
                               '#: `arbitrate_regime(unavailable_reason=...)` 的合法值：健康分因缺真實市場廣度而算不出來。\n'
                               "UNAVAILABLE_REASON_BREADTH: str = 'breadth'\n"
                               '\n'
                               '# ── 門檻 ────────────────────────────────────────────────────────────────\n',
                               '\n'
                               '# ── 門檻 ────────────────────────────────────────────────────────────────\n'),
                              ('\n'
                               '#: 「缺真實市場廣度 ⇒ 未評估」的唯一表示（DEC-074 B）。燈號／regime／is_loaded 同 '
                               '`UNLOADED_VERDICT`。\n'
                               'UNEVALUATED_BREADTH_VERDICT: RegimeVerdict = RegimeVerdict(\n'
                               "    regime='unknown', light=LIGHT_UNKNOWN, "
                               'source=SOURCE_UNEVALUATED_BREADTH,\n'
                               '    defense=False, is_loaded=False,\n'
                               ')\n'
                               '\n'
                               '\n'
                               'def light_for_regime(regime: Any) -> str:\n',
                               '\ndef light_for_regime(regime: Any) -> str:\n'),
                              ('    is_loaded: bool = True,\n'
                               '    unavailable_reason: Optional[str] = None,\n'
                               ') -> RegimeVerdict:\n',
                               '    is_loaded: bool = True,\n) -> RegimeVerdict:\n'),
                              ('        is_loaded:     caller 已知「總經根本沒評估」時傳 False。\n'
                               '        unavailable_reason: health 算不出來的**原因**（DEC-074 B，2026-10-23 新增；預設 '
                               'None\n'
                               '            ⇒ 行為逐位同修前）。只在 `health` 未知時才看：等於 `UNAVAILABLE_REASON_BREADTH`\n'
                               '            ⇒ 回 `UNEVALUATED_BREADTH_VERDICT`；其餘一律 `UNLOADED_VERDICT`。\n'
                               '            health 有值時本參數不影響任何分支（不會因為「有原因」就不判）。\n'
                               '\n',
                               '        is_loaded:     caller 已知「總經根本沒評估」時傳 False。\n\n'),
                              ('        # 拿不到就沒有結論可言 —— 誠實回 unknown，不用 trend_regime 頂替（§1）。\n'
                               '        # DEC-074 B：原因是「缺真實廣度」時只換 `source`（文案／出口分流用），結論同為 unknown。\n'
                               '        if unavailable_reason == UNAVAILABLE_REASON_BREADTH:\n'
                               '            return UNEVALUATED_BREADTH_VERDICT\n'
                               '        return UNLOADED_VERDICT\n',
                               '        # 拿不到就沒有結論可言 —— 誠實回 unknown，不用 trend_regime 頂替（§1）。\n'
                               '        return UNLOADED_VERDICT\n')),
 'shared/signal_thresholds.py': (('**並同批重跑門檻校準**(見 `macro_thresholds.json`)。"""\n'
                                  '\n'
                                  'BREADTH_PROXY_SCORING_ENABLED: bool = False\n'
                                  '"""代理（估算）市場廣度是否可以**計分**。**DEC-074 B（客戶 2026-10-23）：False。**\n'
                                  '\n'
                                  '鏡像同檔 `M1B_M2_LEG_ENABLED` 的處置（DEC-037 M1B 代理不計分先例，不發明第二種機制）。\n'
                                  '客戶原文（DEC-074）：「推估的漲跌家數／proxy breadth 不得計分」「不得把缺少真實 breadth\n'
                                  '當成 0、中性或正常」「不得自行創造新權重重新正規化」「不得因為產品希望『有結論』而補出投資結論」。\n'
                                  '\n'
                                  '現況（2026-10-23 實讀）：`src/data/daily/daily_data_fetchers.fetch_adl` 每一列都是由\n'
                                  '`^TWII` 日內漲跌幅反推的估算家數（`is_proxy=True`），**沒有**真實漲跌家數來源接進計分路徑。\n'
                                  '⇒ 旌旗（ad_ratio 5 日均）與 `market_regime` 的市場廣度腿在本旗標為 False 時：\n'
                                  '  - **可以顯示**（DEC-062 Q5「代理值只顯示、不計分」），數字後綴\n'
                                  '    `shared.macro_provenance.BREADTH_PROXY_VALUE_NOTE`；\n'
                                  '  - **不得**進健康分、大盤評分分子／分母、五桶燈級；\n'
                                  '  - 健康分因此算不出來時 →「⬜ '
                                  '未評估／資料不足」（`shared.regime_arbiter.SOURCE_UNEVALUATED_BREADTH`），\n'
                                  '    **不**以只剩大盤分重新歸一頂替（`HEALTH_WEIGHT_JQ`／`HEALTH_WEIGHT_SCORE` 一字未動）；\n'
                                  '  - DEC-075 D-1(a)：位階一併未評估，**不**退 `macro_state.json` 規則引擎位階。\n'
                                  '\n'
                                  '判定入口一律走 `shared.macro_provenance.jingqi_for_scoring` / '
                                  '`is_breadth_proxy`，\n'
                                  '本旗標由 `src/compute/macro/macro_forward_test.compute_ruleset_hash` 納入 '
                                  'payload（帳本分得出本批前後）。\n'
                                  '\n'
                                  '**復活條件**（缺一不可，與 DEC-074 原文對齊）：(1) 正式（真實）漲跌家數資料來源接上並帶\n'
                                  '`is_proxy=False` 的 provenance，**或**另一套經客戶核准的計算方式；(2) 客戶裁示可計分。\n'
                                  '⛔ 不得為了讓健康分「有數字」而把本旗標翻 True。"""\n'
                                  '\n',
                                  '**並同批重跑門檻校準**(見 `macro_thresholds.json`)。"""\n\n'),),
 'src/compute/macro/macro_forward_test.py': (('    from shared.signal_thresholds import (\n'
                                              '        BREADTH_PROXY_SCORING_ENABLED,\n'
                                              '        CONFIDENCE_SOURCE_COUNT, CONFIDENCE_SOURCE_GROUPS,\n',
                                              '    from shared.signal_thresholds import (\n'
                                              '        CONFIDENCE_SOURCE_COUNT, CONFIDENCE_SOURCE_GROUPS,\n'),
                                             ("        'm1b_leg': M1B_M2_LEG_ENABLED,\n"
                                              '        # DEC-074 B（2026-10-23）：代理廣度是否計分 —— 本批起 health '
                                              '對代理廣度一律未評估，\n'
                                              '        # hash 必須分得出本批前後（計分腿 jq／score／m1b／breadth 才在 hash '
                                              '射程內；五桶燈級不在）。\n'
                                              "        'breadth_proxy_scoring': "
                                              'BREADTH_PROXY_SCORING_ENABLED,\n'
                                              "        'breadth_neutral': MARKET_BREADTH_NEUTRAL_PCT,\n",
                                              "        'm1b_leg': M1B_M2_LEG_ENABLED,\n"
                                              "        'breadth_neutral': MARKET_BREADTH_NEUTRAL_PCT,\n")),
 'src/compute/macro/macro_helpers.py': (("_CONF_LABEL_JINGQI = '旌旗指數 (上漲佔比的 5 日均)'\n"
                                         '\n'
                                         '# DEC-074 B（客戶 2026-10-23）：代理廣度計分入口（L2 → L0，合法下行依賴）。\n'
                                         'from shared.macro_provenance import jingqi_for_scoring as '
                                         '_jingqi_for_scoring  # noqa: E402\n'
                                         '\n'
                                         '#: 旌旗只有代理值、依 DEC-074 不計分時，`missing_sources` 那一項的說法（取代 '
                                         '`_CONF_LABEL_JINGQI`）。\n'
                                         '_BREADTH_PROXY_MISSING_TEXT = (\n'
                                         "    f'{_CONF_LABEL_JINGQI}：市場廣度無真實漲跌家數來源，代理估算值不計分（DEC-074）')\n"
                                         '\n',
                                         "_CONF_LABEL_JINGQI = '旌旗指數 (上漲佔比的 5 日均)'\n\n"),
                                        ("        '請按「🚀 一鍵更新全部數據」重新抓取；在此之前不做多空判斷'),\n"
                                         '    # DEC-074 B（客戶 2026-10-23）：健康分的廣度腿只有代理（估算）家數 → 不計分 → 健康分未評估。\n'
                                         '    # ⛔ 不得寫「重新抓取」「重新載入」之類的指引（計畫 I-4；`CLAUDE.md` §-2 實證第 3 條：\n'
                                         '    #    原因不是一次抓取失敗，重跑一百次也一樣）—— '
                                         '`tests/test_dec074_breadth_gate.py` 守衛。\n'
                                         '    _RA.SOURCE_UNEVALUATED_BREADTH: (\n'
                                         '        TRAFFIC_NEUTRAL,\n'
                                         "        '總經未評估｜資料不足',\n"
                                         "        '⬜ 缺真實市場廣度（漲跌家數），代理估算值依 DEC-074 不計分',\n"
                                         "        '在正式廣度資料接上前不做多空判斷；更新資料不會改變此狀態'),\n"
                                         '}\n',
                                         "        '請按「🚀 一鍵更新全部數據」重新抓取；在此之前不做多空判斷'),\n}\n"),
                                        ('    # 「沒有 jingqi_info」與「有 dict 但 avg 是 None」兩種缺法行為一致。\n'
                                         '    # ── DEC-074 B（客戶 2026-10-23）：代理廣度不計分 '
                                         '─────────────────────────\n'
                                         '    # 計分端一律經 L0 `jingqi_for_scoring`（鏡像 M1B '
                                         '`m1b_m2_for_scoring`）：代理 ⇒ None ⇒\n'
                                         '    # 走「旌旗缺席」路徑；顯示用原值仍在呼叫端的 `jingqi_info`（I-5，DEC-062 Q5）。\n'
                                         '    _jq_scoring = _jingqi_for_scoring(jingqi_info) or {}\n'
                                         '    _jq_proxy_dropped = bool(_jq) and not _jq_scoring and '
                                         "_safe_float(_jq.get('avg')) is not None\n"
                                         "    _jqavg = _safe_float(_jq_scoring.get('avg'))\n"
                                         "    # ── v19.175 P0(實機 2/2 重現):`cl_data['inst']` 可能是 **None** "
                                         '──────────\n',
                                         '    # 「沒有 jingqi_info」與「有 dict 但 avg 是 None」兩種缺法行為一致。\n'
                                         "    _jqavg = _safe_float(_jq.get('avg'))\n"
                                         "    # ── v19.175 P0(實機 2/2 重現):`cl_data['inst']` 可能是 **None** "
                                         '──────────\n'),
                                        ('    # **不是** 0 分(0 分會被判成最強利空),也不是 🟡(🟡 是一個市場判斷)。\n'
                                         '    # ── DEC-074 B（客戶 2026-10-23，行為變更，有意識的修改，⛔ 不是漏刪）──────────\n'
                                         '    # ~~旌旗缺席 ⇒ 只剩大盤分重新歸一~~ —— 客戶原文「不得自行創造新權重重新正規化」\n'
                                         '    # 「受 breadth 影響且無法依既有正式規則可靠計算的健康分 →『⬜ 未評估／資料不足』」。\n'
                                         '    # ⇒ 旌旗（廣度腿）缺席（含代理被 `jingqi_for_scoring` 擋下）一律 health=None。\n'
                                         '    #   舊做法的理由（v19.177：缺項不捏 50）仍成立；被權衡掉的只是「歸一出一個分數」。\n'
                                         '    #   大盤評分缺席而旌旗真值在（D-3）不屬「受 breadth 影響」→ 既有歸一不動（現況不可達：\n'
                                         '    #   正式 breadth 到位前 jqavg 恆 None）。\n'
                                         '    _breadth_unavailable = _jqavg is None\n'
                                         '    if _w_sum <= 0 or _breadth_unavailable:\n'
                                         '        _health = None\n',
                                         '    # **不是** 0 分(0 分會被判成最強利空),也不是 🟡(🟡 是一個市場判斷)。\n'
                                         '    if _w_sum <= 0:\n'
                                         '        _health = None\n'),
                                        ('    # 的 legacy 決策樹對拍測試)。\n'
                                         '    # DEC-074 B：health 算不出來「只因為缺廣度」（大盤評分本身在）⇒ 原因標 breadth\n'
                                         '    # （文案不再叫人重抓）。兩條腿都缺 ⇒ 既有 `SOURCE_UNLOADED`（其餘輸入也缺，重抓仍可能補上大盤分）。\n'
                                         '    _health_unavailable_reason = (\n'
                                         '        _RA.UNAVAILABLE_REASON_BREADTH\n'
                                         '        if (_health is None and _breadth_unavailable and '
                                         '_score_pct is not None) else None)\n'
                                         '    _verdict = _RA.arbitrate_regime(\n',
                                         '    # 的 legacy 決策樹對拍測試)。\n    _verdict = _RA.arbitrate_regime(\n'),
                                        ('        health_defense_threshold=_h_thr, bull_min_score=_s_thr,\n'
                                         '        unavailable_reason=_health_unavailable_reason,\n'
                                         '    )\n',
                                         '        health_defense_threshold=_h_thr, bull_min_score=_s_thr,\n'
                                         '    )\n'),
                                        ('    #    凍結走**列名**這條路（畫面本來就會逐項印出 `missing_sources`）。\n'
                                         '    # DEC-074 B：旌旗**有代理值、被擋下不計分**時，缺失那一項據實寫原因（不是「沒抓到」）。\n'
                                         '    #   同一項替換、不另加一項 ⇒ 項數與 `conf` 一致。\n'
                                         '    if _jq_proxy_dropped:\n'
                                         '        _missing = [(_BREADTH_PROXY_MISSING_TEXT if _m == '
                                         '_CONF_LABEL_JINGQI else _m)\n'
                                         '                    for _m in _missing]\n'
                                         '    if _fut_frozen:\n',
                                         '    #    凍結走**列名**這條路（畫面本來就會逐項印出 `missing_sources`）。\n'
                                         '    if _fut_frozen:\n'),
                                        ("        'action': _action, 'sub': _sub, 'health': _health,\n"
                                         '        # ~~v19.177:True = 健康評分少了旌旗(廣度)那條腿,僅由大盤評分推算。~~\n'
                                         '        # 📌 DEC-074 B（2026-10-23，有意識的更正，⛔ 不是漏刪）：旌旗缺席自本批起 '
                                         'health=None\n'
                                         '        #   （不再「僅由大盤評分推算」）；True 仍表示「至少一條腿缺席」，鍵與 bool 語意不變（D-4）。\n'
                                         '        # 畫面須據此標示(handlers._render_traffic_light),不可靜默(§1)。\n'
                                         "        'health_partial': _health_partial,\n"
                                         '        # DEC-074 B schema-additive（D-4）：health 為 None '
                                         "的**原因**；'breadth' ＝ 缺真實市場廣度\n"
                                         '        # （代理不計分），None ＝ 有健康分、或其餘原因（沿用 `regime_source` 判）。\n'
                                         "        'health_unavailable_reason': _health_unavailable_reason,\n"
                                         "        'defense': _defense, 'score': _score, 'jqavg': _jqavg,\n",
                                         "        'action': _action, 'sub': _sub, 'health': _health,\n"
                                         '        # v19.177:True = 健康評分少了旌旗(廣度)那條腿,僅由大盤評分推算。\n'
                                         '        # 畫面須據此標示(handlers._render_traffic_light),不可靜默(§1)。\n'
                                         "        'health_partial': _health_partial,\n"
                                         "        'defense': _defense, 'score': _score, 'jqavg': _jqavg,\n"),
                                        ('\n'
                                         '    # DEC-074 B（客戶 2026-10-23）：市場廣度兩盞（jingqi／adl）只有代理（估算）家數時，比照上面\n'
                                         '    # M1B（DL-f1-s17）：**值照顯示＋後綴代理註記、燈走既有 gray（不判燈級、不進桶 '
                                         'worst-of）**，\n'
                                         '    # 側車同步帶 `is_proxy=True`（只在代理且有值時加；非代理時側車逐鍵不變）——\n'
                                         '    # v2 今天頁與 `tab_macro_v2.build_rows` 讀同一個側車判定，不另開取數路徑。\n'
                                         '    # 判定：jingqi 看 `jingqi_info` 的明確旗標（L0 `is_breadth_proxy`）；adl 看 '
                                         "`cl_data['adl']`\n"
                                         '    # 末列 `is_proxy`（L0 `adl_df_is_proxy`，缺欄 fail-safe 視同代理）。計分開關在 '
                                         'L0。\n'
                                         '    from shared.macro_provenance import (\n'
                                         '        BREADTH_PROXY_VALUE_NOTE, adl_df_is_proxy, '
                                         'is_breadth_proxy,\n'
                                         '    )\n'
                                         '    from shared.signal_thresholds import '
                                         'BREADTH_PROXY_SCORING_ENABLED\n'
                                         '    _breadth_proxy_keys: set = set()\n'
                                         '    if not BREADTH_PROXY_SCORING_ENABLED:\n'
                                         '        if is_breadth_proxy(jingqi_info):\n'
                                         '            _breadth_proxy_keys.add("jingqi")\n'
                                         '        _adl_df_bp = _g(cl_data, "adl")\n'
                                         '        if _adl_df_bp is not None and '
                                         'adl_df_is_proxy(_adl_df_bp):\n'
                                         '            _breadth_proxy_keys.add("adl")\n'
                                         '    for _bk in _breadth_proxy_keys:\n'
                                         '        if isinstance(_rd.get(_bk), dict) and '
                                         '_rd[_bk].get("state") == "ok":\n'
                                         '            _rd[_bk]["is_proxy"] = True\n'
                                         '\n'
                                         '    out: dict = {}\n',
                                         '\n    out: dict = {}\n'),
                                        ('                _value_str = f"{_value_str}{_m1b_badge}"\n'
                                         '            _is_breadth_proxy_lamp = s.key in _breadth_proxy_keys\n'
                                         '            if _is_breadth_proxy_lamp and v is not None:\n'
                                         '                _value_str = '
                                         'f"{_value_str}{BREADTH_PROXY_VALUE_NOTE}"\n'
                                         '            details.append({\n',
                                         '                _value_str = f"{_value_str}{_m1b_badge}"\n'
                                         '            details.append({\n'),
                                        ('                # 顯示（上面 value_str 帶註記），但燈號走既有未載入 gray —— 不進桶等級 / '
                                         'headline。\n'
                                         '                # DEC-074 B：市場廣度兩盞代理時同一處置。\n'
                                         '                "danger": (classify_danger(None, s)\n'
                                         '                           if (s.key == "m1b_m2_gap" and '
                                         '_m1b_badge) or _is_breadth_proxy_lamp\n'
                                         '                           else classify_danger(v, s)),\n',
                                         '                # 顯示（上面 value_str 帶註記），但燈號走既有未載入 gray —— 不進桶等級 / '
                                         'headline。\n'
                                         '                "danger": (classify_danger(None, s)\n'
                                         '                           if s.key == "m1b_m2_gap" and '
                                         '_m1b_badge\n'
                                         '                           else classify_danger(v, s)),\n')),
 'src/services/jingqi_calc.py': (('- 三段燈號(BULL/NEUTRAL/BEAR SSOT from shared.signal_thresholds)\n'
                                  "- 寫 session_state['jingqi_info'] ~~7~~ 8 keys(DEC-074 B 加 "
                                  '`is_proxy`;供戰情概覽/作戰室/section_inputs 讀;\n'
                                  '  v19.84 刪 pct20/60/120/240 — 該 4 鍵為 ratio×0.9/0.8/0.7 捏造值且全 repo 0 讀者,\n',
                                  '- 三段燈號(BULL/NEUTRAL/BEAR SSOT from shared.signal_thresholds)\n'
                                  "- 寫 session_state['jingqi_info'] 7 keys(供戰情概覽/作戰室/section_inputs 讀;\n"
                                  '  v19.84 刪 pct20/60/120/240 — 該 4 鍵為 ratio×0.9/0.8/0.7 捏造值且全 repo 0 '
                                  '讀者,\n'),
                                 ('from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW\n'
                                  'from shared.macro_provenance import adl_rows_any_proxy  # DEC-074 '
                                  'B：代理旗標判定（L0，fail-safe）\n'
                                  'from shared.signal_thresholds import (\n',
                                  'from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW\n'
                                  'from shared.signal_thresholds import (\n'),
                                 ("    成功時寫 `st.session_state['jingqi_info']` = "
                                  '{avg/pos/regime/color/label/\n'
                                  '    total/source/is_proxy} 共 8 鍵（DEC-074 B 2026-10-23 加 `is_proxy`；原為 7 '
                                  '鍵）。\n'
                                  '    ⚠️ v19.177 更正:此處原本還列著 `pct20/pct60/pct120/pct240` —— 那 4 鍵早在\n',
                                  "    成功時寫 `st.session_state['jingqi_info']` = "
                                  '{avg/pos/regime/color/label/\n'
                                  '    total/source} 共 7 鍵。\n'
                                  '    ⚠️ v19.177 更正:此處原本還列著 `pct20/pct60/pct120/pct240` —— 那 4 鍵早在\n'),
                                 ('    docstring 卻沒跟著改,與實際寫入的鍵集合矛盾(鍵契約由\n'
                                  '    tests/test_p0c_breadth_naming.py::_JQ_CONTRACT_KEYS 釘住;DEC-074 B 起 8 '
                                  '鍵)。\n'
                                  '    全敗(無 ADL + 無大盤資料)→ 不寫(誠實顯示未載入,§1)。\n',
                                  '    docstring 卻沒跟著改,與實際寫入的鍵集合矛盾(鍵契約由\n'
                                  '    tests/test_p0c_breadth_naming.py::_JQ_CONTRACT_KEYS 釘住 7 鍵)。\n'
                                  '    全敗(無 ADL + 無大盤資料)→ 不寫(誠實顯示未載入,§1)。\n'),
                                 ('    _jq_ratio = None\n'
                                  '    # DEC-074 B（客戶 2026-10-23）：代理旗標。主源被平均的那 N 列任一為估算（或缺 `is_proxy` 欄，\n'
                                  '    # fail-safe）⇒ True；「大盤估算」備援恆 True。`avg` 照算供顯示（DEC-062 Q5 只顯示不計分）。\n'
                                  '    _jq_is_proxy = True\n'
                                  "    if df_adl_raw is not None and not df_adl_raw.empty and 'ad_ratio' in "
                                  'df_adl_raw.columns:\n',
                                  '    _jq_ratio = None\n'
                                  "    if df_adl_raw is not None and not df_adl_raw.empty and 'ad_ratio' in "
                                  'df_adl_raw.columns:\n'),
                                 ("        _jq_ratio = float(df_adl_raw['ad_ratio'].tail(5).mean())\n"
                                  '        # 看的就是上一行被平均的那 5 列（口徑 SSOT 是上一行字面，`tests/test_p1b_*` 釘住）。\n'
                                  '        _jq_is_proxy = adl_rows_any_proxy(df_adl_raw, 5)\n'
                                  '    else:\n',
                                  "        _jq_ratio = float(df_adl_raw['ad_ratio'].tail(5).mean())\n"
                                  '    else:\n'),
                                 ("                _jq_ratio_src = '大盤估算'\n"
                                  '                _jq_is_proxy = True   # 由大盤上漲天數推估，非家數 ⇒ 恆為代理\n'
                                  '\n',
                                  "                _jq_ratio_src = '大盤估算'\n\n"),
                                 ("            'source': _jq_ratio_src,\n"
                                  '            # DEC-074 B schema-additive 第 8 '
                                  '鍵（`tests/test_p0c_breadth_naming.py::_JQ_CONTRACT_KEYS`）：\n'
                                  '            # True ⇒ 計分端經 `shared.macro_provenance.jingqi_for_scoring` 拿到 '
                                  'None（不計分）。\n'
                                  "            'is_proxy': bool(_jq_is_proxy),\n"
                                  '        }\n',
                                  "            'source': _jq_ratio_src,\n        }\n")),
 'src/services/macro_refresh_service.py': (('        if _wr_res.written:\n'
                                            '            # DEC-074 B／DEC-075 '
                                            'D-1(a)（2026-10-23）：健康分未評估的**原因**是「缺真實市場廣度」時，\n'
                                            '            #   下面那句既有說明（「兩條腿都缺」「位階會改讀 macro_state.json」）兩半都不屬實 '
                                            '⇒ 換成屬實的那句；\n'
                                            '            #   其餘情形逐字照舊。⛔ 不寫「重新抓取」之類的指引（重跑不會讓代理值變成可計分）。\n'
                                            '            from shared import regime_arbiter as _RA_wr\n'
                                            '            _wr_breadth = (_wr_res.health_missing\n'
                                            '                           and '
                                            '(st.session_state.get("warroom_summary") or '
                                            '{}).get("regime_source")\n'
                                            '                           == '
                                            '_RA_wr.SOURCE_UNEVALUATED_BREADTH)\n'
                                            '            _step(STEP_WARROOM, True,\n'
                                            '                  "寫入 warroom_summary"\n'
                                            '                  + ("（⚠️ 健康分因缺真實市場廣度（漲跌家數）未評估 —— 代理估算值依 '
                                            'DEC-074 不計分："\n'
                                            '                     "建議持股的姿態帶與市場位階一併未評估（DEC-075，不改讀 '
                                            'macro_state.json）；"\n'
                                            '                     "更新資料不會改變此狀態）"\n'
                                            '                     if _wr_breadth else\n'
                                            '                     "（⚠️ 健康分兩條腿都缺 → `get_macro_state()` 把這份 '
                                            'warroom 視同**未載入**："\n'
                                            '                     "建議持股的姿態帶算不出來；市場位階若有可用的 macro_state.json '
                                            '會改讀它）"\n',
                                            '        if _wr_res.written:\n'
                                            '            _step(STEP_WARROOM, True,\n'
                                            '                  "寫入 warroom_summary"\n'
                                            '                  + ("（⚠️ 健康分兩條腿都缺 → `get_macro_state()` 把這份 '
                                            'warroom 視同**未載入**："\n'
                                            '                     "建議持股的姿態帶算不出來；市場位階若有可用的 macro_state.json '
                                            '會改讀它）"\n'),),
 'src/services/macro_state_locker.py': (('    _wr_ok = bool(_wr) and '
                                         '_is_finite_number(_wr.get("health_score"))\n'
                                         '    # ── DEC-075 D-1(a)（客戶 2026-10-23，行為變更，有意識的修改，⛔ '
                                         '不是漏刪）──────────────\n'
                                         '    # 上一行 `_wr_ok`（C1 v19.182「NaN 視同未載入」）**本身一字未改**；新增的是它的一個例外讀法：\n'
                                         '    # warroom 健康分非有限數、**且** warroom 自己標明原因是「缺真實市場廣度」\n'
                                         '    # （`regime_source == SOURCE_UNEVALUATED_BREADTH`，DEC-074 B）⇒ '
                                         'warroom **仍是權威來源**：\n'
                                         "    # 位階一併未評估（`regime='unknown'`、`is_loaded=False`），⛔ 不退 "
                                         '`macro_state.json`\n'
                                         '    # 規則引擎位階（客戶原文「不允許…靜默 fallback 到另一套規則引擎產生位階結論」）。\n'
                                         '    # ⚠️ 只限 breadth 原因：其他原因的 health 非有限（F1 '
                                         '三源全敗＝`SOURCE_UNLOADED`、上游 NaN…）\n'
                                         '    # 照舊視同 warroom 不存在、退檔案位階（C1 v19.182／AUD-C22 其餘語意不動）。\n'
                                         '    # 舊理由（「NaN 不是一個健康分」）仍成立；被權衡掉的只是「health 缺席 ⇒ 一律退檔」。\n'
                                         '    _wr_breadth = (bool(_wr) and not _wr_ok\n'
                                         '                   and _wr.get("regime_source") == '
                                         '_RA.SOURCE_UNEVALUATED_BREADTH)\n'
                                         '    _file_ok = bool(_file) and _file.get("market_regime") not in '
                                         '(None, "系統異常")\n',
                                         '    _wr_ok = bool(_wr) and '
                                         '_is_finite_number(_wr.get("health_score"))\n'
                                         '    _file_ok = bool(_file) and _file.get("market_regime") not in '
                                         '(None, "系統異常")\n'),
                                        ('        _file_ok = False\n'
                                         '    # DEC-075 D-1(a)：`_wr_breadth` 時 warroom 仍是權威來源（位階＝未評估）⇒ 下方 '
                                         'strict 拋錯／`file_error`\n'
                                         '    #   判斷視同「有來源撐住」；回傳的 `is_loaded` 在組 `_out` 前另行改回 False（見下）。\n'
                                         '    _is_loaded = _wr_ok or _file_ok or _wr_breadth\n'
                                         '    # 批 Z36（Q-z19，客戶 2026-10-10 核准 A）：規則引擎 ~~8 項~~數值輸入**全缺**時落檔的 '
                                         'fail-safe（「系統異常」＋\n',
                                         '        _file_ok = False\n'
                                         '    _is_loaded = _wr_ok or _file_ok\n'
                                         '    # 批 Z36（Q-z19，客戶 2026-10-10 核准 A）：規則引擎 ~~8 項~~數值輸入**全缺**時落檔的 '
                                         'fail-safe（「系統異常」＋\n'),
                                        ('        _file_error = _strict_detail\n'
                                         '    # DEC-075 D-1(a)：breadth 未評估時 warroom 同樣撐得住位階（＝未評估）⇒ 檔讀壞不拋、改帶 '
                                         '`file_error`（同上）。\n'
                                         '    if (strict and _wr_breadth and not _file_ok and '
                                         'os.path.exists(state_file_path)\n'
                                         '            and not _file_expired and not _file_no_data):\n'
                                         '        _file_error = _strict_detail\n'
                                         '    # 📌 AUD-C21 B1（2026-10-16，AI 總管決策，有意識的變更，⛔ 不是漏改）：旗標開（新 UI）＋ '
                                         'warroom 可用時，\n',
                                         '        _file_error = _strict_detail\n'
                                         '    # 📌 AUD-C21 B1（2026-10-16，AI 總管決策，有意識的變更，⛔ 不是漏改）：旗標開（新 UI）＋ '
                                         'warroom 可用時，\n'),
                                        ('    if require_valid_risk_cap and _wr_ok:\n'
                                         '        _file_error = ""\n'
                                         '    if require_valid_risk_cap and _wr_breadth:   # DEC-075 '
                                         'D-1(a)：位階同樣不靠舊檔（同上）\n'
                                         '        _file_error = ""\n',
                                         '    if require_valid_risk_cap and _wr_ok:\n'
                                         '        _file_error = ""\n'),
                                        ('            _regime, _light, _source = _v.regime, _v.light, '
                                         '_v.source\n'
                                         '    elif _wr_breadth:\n'
                                         '        # DEC-075 D-1(a)：缺真實廣度 ⇒ 位階未評估（⛔ 不退檔案位階）。\n'
                                         '        _regime = _RA.UNEVALUATED_BREADTH_VERDICT.regime\n'
                                         '        _light = _RA.UNEVALUATED_BREADTH_VERDICT.light\n'
                                         '        _source = _RA.UNEVALUATED_BREADTH_VERDICT.source\n'
                                         '    elif _file_ok:\n',
                                         '            _regime, _light, _source = _v.regime, _v.light, '
                                         '_v.source\n'
                                         '    elif _file_ok:\n'),
                                        ('        _health is not None and float(_health) < float(_HD))\n'
                                         '\n'
                                         '    if _wr_breadth:\n'
                                         '        # DEC-075 D-1(a)：缺真實廣度 ⇒ 位階未評估 ⇒ 對外 '
                                         '`is_loaded=False`（姿態帶／濾網走既有未評估路徑）。\n'
                                         '        _is_loaded = False\n'
                                         '\n',
                                         '        _health is not None and float(_health) < float(_HD))\n\n')),
 'src/services/market_assessment_apply.py': (('from shared.macro_provenance import is_m1b_m2_proxy  # '
                                              'DL-f1-s17／s23：代理值不計分（L0 SSOT）\n'
                                              'from shared.macro_provenance import adl_df_is_proxy  # '
                                              'DEC-074 B：代理廣度不計分（L0 SSOT，fail-safe）\n'
                                              'from shared.inst_net import is_net_observed  # 批 '
                                              'Z35（Q-z16）：外資淨額未觀測（L1 預填／L3 補零推出）不當真值\n',
                                              'from shared.macro_provenance import is_m1b_m2_proxy  # '
                                              'DL-f1-s17／s23：代理值不計分（L0 SSOT）\n'
                                              'from shared.inst_net import is_net_observed  # 批 '
                                              'Z35（Q-z16）：外資淨額未觀測（L1 預填／L3 補零推出）不當真值\n'),
                                             ('        _ad_ratio_loaded = None\n'
                                              '        # DEC-074 B（客戶 2026-10-23）：末列為代理（估算）家數、或缺 `is_proxy` '
                                              '欄（fail-safe）\n'
                                              '        # ⇒ 值交給 L3 '
                                              '只顯示（`ad_ratio_display`）、**不計分**（`ad_ratio=None`、不進分母、不列缺失）。\n'
                                              '        _ad_ratio_is_proxy = False\n'
                                              '        _ad_ratio_display = None\n'
                                              '        try:\n',
                                              '        _ad_ratio_loaded = None\n        try:\n'),
                                             ('                if _v_adr == _v_adr:  # NaN 自身不等於自身\n'
                                              '                    if adl_df_is_proxy(df_adl):\n'
                                              '                        _ad_ratio_is_proxy = True\n'
                                              '                        _ad_ratio_display = float(_v_adr)\n'
                                              '                    else:\n'
                                              '                        _ad_ratio_loaded = float(_v_adr)\n'
                                              '        except Exception as _e_adr:\n'
                                              "            print(f'[市場評估] ad_ratio "
                                              "解析失敗(不納入評分):{type(_e_adr).__name__}: {_e_adr}')\n"
                                              '        # 只在代理時才多帶兩個 kwarg（非代理時呼叫形狀逐字同修前；同 M1B '
                                              '側車「只在代理時才加」的慣例）。\n'
                                              "        _adr_proxy_kw = ({'ad_ratio_is_proxy': True, "
                                              "'ad_ratio_display': _ad_ratio_display}\n"
                                              '                         if _ad_ratio_is_proxy else {})\n'
                                              '        _mkt_loaded = get_market_assessment(\n',
                                              '                if _v_adr == _v_adr:  # NaN 自身不等於自身\n'
                                              '                    _ad_ratio_loaded = float(_v_adr)\n'
                                              '        except Exception as _e_adr:\n'
                                              "            print(f'[市場評估] ad_ratio "
                                              "解析失敗(不納入評分):{type(_e_adr).__name__}: {_e_adr}')\n"
                                              '        _mkt_loaded = get_market_assessment(\n'),
                                             ('            foreign_net_unobserved=_foreign_unobserved,\n'
                                              '            **_adr_proxy_kw,\n'
                                              '        )\n',
                                              '            foreign_net_unobserved=_foreign_unobserved,\n'
                                              '        )\n'),
                                             ('                                            '
                                              'm1b_m2_is_proxy=_m1b2_is_proxy,\n'
                                              '                                            '
                                              'foreign_net_unobserved=_foreign_unobserved,\n'
                                              '                                            **_adr_proxy_kw)\n'
                                              '            if _mkt_fb:\n',
                                              '                                            '
                                              'm1b_m2_is_proxy=_m1b2_is_proxy,\n'
                                              '                                            '
                                              'foreign_net_unobserved=_foreign_unobserved)\n'
                                              '            if _mkt_fb:\n')),
 'src/services/market_strategy.py': (('# v18.449:市場廣度中性門檻 SSOT(原 inline `1.0`，尺度語意錯誤，見下方 market_regime '
                                      'docstring）\n'
                                      'from shared.signal_thresholds import (\n'
                                      '    BREADTH_PROXY_SCORING_ENABLED, M1B_M2_LEG_ENABLED, '
                                      'MARKET_BREADTH_NEUTRAL_PCT,\n'
                                      ')\n'
                                      'from shared.macro_provenance import M1B_PROXY_VALUE_NOTE  # '
                                      'DL-f1-s23：代理註記（L0 SSOT，K1）\n'
                                      '\n'
                                      '#: `get_market_assessment` 算 MA200（年線）所需的最少 K 棒數（與 rolling 視窗同一個數）。\n'
                                      'MA200_WINDOW_DAYS: int = 200\n'
                                      'from shared.dated_value import iso_date_or_none  # 批 Z62：index_as_of '
                                      '收斂（L0）\n',
                                      '# v18.449:市場廣度中性門檻 SSOT(原 inline `1.0`，尺度語意錯誤，見下方 market_regime '
                                      'docstring）\n'
                                      'from shared.signal_thresholds import M1B_M2_LEG_ENABLED, '
                                      'MARKET_BREADTH_NEUTRAL_PCT\n'
                                      'from shared.macro_provenance import M1B_PROXY_VALUE_NOTE  # '
                                      'DL-f1-s23：代理註記（L0 SSOT，K1）\n'
                                      'from shared.dated_value import iso_date_or_none  # 批 Z62：index_as_of '
                                      '收斂（L0）\n'),
                                     ('                  ma120_rising=False, ma120_falling=False,\n'
                                      '                  m1b_m2_is_proxy=False, '
                                      'foreign_net_unobserved=False,\n'
                                      '                  ad_ratio_is_proxy=False, ad_ratio_display=None):\n'
                                      '    """\n',
                                      '                  ma120_rising=False, ma120_falling=False,\n'
                                      '                  m1b_m2_is_proxy=False, '
                                      'foreign_net_unobserved=False):\n'
                                      '    """\n'),
                                     ('                 腿停用時 chip 照舊顯示數字並後綴 L0 既有註記，腿啟用時走既有缺值路徑（不出、不計分母）。\n'
                                      '    ad_ratio_is_proxy: bool — 市場廣度只有代理（估算）家數（呼叫端以 L0 '
                                      '`adl_df_is_proxy` 判）。\n'
                                      '                 DEC-074 B（客戶 2026-10-23）：代理廣度**不計分** —— `ad_ratio` '
                                      '一律視為 None\n'
                                      '                 （不進分子／分母），**不**列入 `missing_factors`（「代理不計分」≠「缺失」，同 '
                                      'M1B 停用腿），\n'
                                      '                 改出一行「⬜ 市場廣度 …（^TWII 估算代理）— 不計分」signal。\n'
                                      '    ad_ratio_display: float | None — 代理時要顯示的數值（只進 signal 文字，不計分）。\n'
                                      '    """\n'
                                      '    _breadth_proxy_dropped = bool(ad_ratio_is_proxy) and not '
                                      'BREADTH_PROXY_SCORING_ENABLED\n'
                                      '    if _breadth_proxy_dropped:\n'
                                      '        if ad_ratio_display is None:\n'
                                      '            ad_ratio_display = ad_ratio\n'
                                      '        ad_ratio = None        # DEC-074 B：代理值不得進分數 / 分母\n'
                                      '    if m1b_m2_is_proxy and M1B_M2_LEG_ENABLED:\n',
                                      '                 腿停用時 chip 照舊顯示數字並後綴 L0 既有註記，腿啟用時走既有缺值路徑（不出、不計分母）。\n'
                                      '    """\n'
                                      '    if m1b_m2_is_proxy and M1B_M2_LEG_ENABLED:\n'),
                                     ('    # ④ 市場廣度（選填，不傳則略過，同 m1b_m2_gap 慣例 — 未接真值前不假裝中性）\n'
                                      '    if _breadth_proxy_dropped:\n'
                                      '        # DEC-074 B：停用 ≠ 缺資料 —— 上游給了一個估算值，只是不准計分；要說出來（§1）。\n'
                                      "        _adr_txt = (f'{float(ad_ratio_display):.1f}%' if "
                                      "ad_ratio_display is not None else '—')\n"
                                      "        signals.append(f'⬜ 市場廣度 {_adr_txt}（^TWII 估算代理）— 不計分')\n"
                                      '    elif ad_ratio is not None:\n'
                                      '        if ad_ratio > MARKET_BREADTH_NEUTRAL_PCT:\n',
                                      '    # ④ 市場廣度（選填，不傳則略過，同 m1b_m2_gap 慣例 — 未接真值前不假裝中性）\n'
                                      '    if ad_ratio is not None:\n'
                                      '        if ad_ratio > MARKET_BREADTH_NEUTRAL_PCT:\n'),
                                     ('    _missing_factors = []\n'
                                      '    # DEC-074 B：代理不計分 ≠ 缺失（同下方 M1B 停用腿的處理）⇒ 不列。\n'
                                      '    if ad_ratio is None and not _breadth_proxy_dropped:\n'
                                      "        _missing_factors.append('市場廣度')\n",
                                      '    _missing_factors = []\n'
                                      '    if ad_ratio is None:\n'
                                      "        _missing_factors.append('市場廣度')\n"),
                                     ('    score = 0; signals = []\n'
                                      '    # DH-TWII-MA200（DEC-075 批 A）：`ma200=None`（K 棒不足／含缺值）⇒ 年線項未評估，\n'
                                      '    # 且 `status`／`confidence` 為 None —— 年線是三因子裡權重最大的一項（+2／滿分 5），\n'
                                      '    # 拿掉它再用 4／2 分切點判多空，等於用剩下兩項補出一個結論（DEC-074「不得補結論」同精神）。\n'
                                      '    _ma200_known = ma200 is not None\n'
                                      '    if not _ma200_known:\n'
                                      "        signals.append('⬜ 年線資料不足（未評估）')\n"
                                      '    elif index_price > ma200:\n'
                                      "        score += 2; signals.append('✅ 站上年線 (+2)')\n",
                                      '    score = 0; signals = []\n'
                                      '    if index_price > ma200:\n'
                                      "        score += 2; signals.append('✅ 站上年線 (+2)')\n"),
                                     ('    confidence = min(100, score * 20) if score >= 4 else (score * 15 '
                                      'if score >= 2 else max(0, 30 - score*10))\n'
                                      '    if not _ma200_known:\n'
                                      '        status, confidence = None, None\n'
                                      "    return {'score': score, 'max_score': 5, 'status': status,\n",
                                      '    confidence = min(100, score * 20) if score >= 4 else (score * 15 '
                                      'if score >= 2 else max(0, 30 - score*10))\n'
                                      "    return {'score': score, 'max_score': 5, 'status': status,\n"),
                                     ('                          m1b_m2_gap=None, m1b_m2_prev=None, '
                                      'ad_ratio=None,\n'
                                      '                          m1b_m2_is_proxy=False, '
                                      'foreign_net_unobserved=False,\n'
                                      '                          ad_ratio_is_proxy=False, '
                                      'ad_ratio_display=None):\n'
                                      '    """\n',
                                      '                          m1b_m2_gap=None, m1b_m2_prev=None, '
                                      'ad_ratio=None,\n'
                                      '                          m1b_m2_is_proxy=False, '
                                      'foreign_net_unobserved=False):\n'
                                      '    """\n'),
                                     ('    ad_ratio:    市場廣度(0-100% 上漲家數佔比)；None = 不納入評分(v18.449 新增)\n'
                                      '    ad_ratio_is_proxy / ad_ratio_display: DEC-074 B 代理廣度（見 '
                                      '`market_regime`）；原樣透傳。\n'
                                      '    """\n',
                                      '    ad_ratio:    市場廣度(0-100% 上漲家數佔比)；None = 不納入評分(v18.449 新增)\n'
                                      '    """\n'),
                                     ('    ma60  = float(_close.rolling(60).mean().iloc[-1])  if '
                                      'len(df_index) >= 60  else current_price\n'
                                      '    # ── DH-TWII-MA200（DEC-075 批 A，2026-10-23，行為變更，有意識的修改，⛔ '
                                      '不是漏刪）────────\n'
                                      '    # ~~ma200 = ... if len(df_index) >= 200 else current_price~~\n'
                                      '    # 舊寫法在 K 棒不足 200 根時拿**現價頂替年線**（§1「自行估一個合理值」）：預設抓取窗\n'
                                      "    # `range_='9mo'` 的台股交易日恆不足 200 根 ⇒ `market_score` 的 `index_price "
                                      '> ma200` 恆 False\n'
                                      '    # ⇒ 年線項恆「❌ 跌破年線」，`status`／`confidence` 跟著被拉成空頭側 —— 一個沒算過的結論。\n'
                                      '    # 現行：不足 ⇒ `ma200=None`＋`ma200_status` 帶原因；年線項「⬜ '
                                      '未評估」，`status`／`confidence`\n'
                                      '    # 為 None（不以剩下兩項補出多空結論）。⛔ 不改抓取窗（與 `VN1-PG-L-PIT-GAPS`(a) 重疊，另批）。\n'
                                      '    _ma200_status = None\n'
                                      '    if len(df_index) >= MA200_WINDOW_DAYS:\n'
                                      '        _ma200_raw = '
                                      '_close.rolling(MA200_WINDOW_DAYS).mean().iloc[-1]\n'
                                      '        ma200 = None if pd.isna(_ma200_raw) else float(_ma200_raw)\n'
                                      '        if ma200 is None:\n'
                                      "            _ma200_status = f'年線無法計算（近 {MA200_WINDOW_DAYS} 根收盤含缺值）'\n"
                                      '    else:\n'
                                      '        ma200 = None\n'
                                      "        _ma200_status = (f'年線未評估：大盤 K 棒僅 {len(df_index)} 根，'\n"
                                      "                         f'不足 {MA200_WINDOW_DAYS} 根（不以現價頂替）')\n"
                                      '    # P1 2026-08-27:原本是\n',
                                      '    ma60  = float(_close.rolling(60).mean().iloc[-1])  if '
                                      'len(df_index) >= 60  else current_price\n'
                                      '    ma200 = float(_close.rolling(200).mean().iloc[-1]) if '
                                      'len(df_index) >= 200 else current_price\n'
                                      '    # P1 2026-08-27:原本是\n'),
                                     ('        m1b_m2_is_proxy=m1b_m2_is_proxy, '
                                      'foreign_net_unobserved=foreign_net_unobserved,\n'
                                      '        ad_ratio_is_proxy=ad_ratio_is_proxy, '
                                      'ad_ratio_display=ad_ratio_display,\n'
                                      '        ma60_above_3d=ma60_above_3d, ma60_below_3d=ma60_below_3d,\n',
                                      '        m1b_m2_is_proxy=m1b_m2_is_proxy, '
                                      'foreign_net_unobserved=foreign_net_unobserved,\n'
                                      '        ma60_above_3d=ma60_above_3d, ma60_below_3d=ma60_below_3d,\n'),
                                     ("    result['ma120']          = round(ma120, 2)\n"
                                      "    result['ma200']          = (round(ma200, 2) if ma200 is not None "
                                      'else None)\n'
                                      '    # DH-TWII-MA200 schema-additive：年線為 None 的原因（有值時 None）。\n'
                                      "    result['ma200_status']   = _ma200_status\n"
                                      "    result['index_below_ma5'] = current_price < ma5\n",
                                      "    result['ma120']          = round(ma120, 2)\n"
                                      "    result['ma200']          = round(ma200, 2)\n"
                                      "    result['index_below_ma5'] = current_price < ma5\n")),
 'src/services/reconcile_service.py': (('from shared.inst_net import is_net_observed  # 批 Z33：外資淨額未觀測（L1 '
                                        '預填／L3 補零推出）不當真值\n'
                                        'from shared.macro_provenance import jingqi_for_scoring  # DEC-074 '
                                        'B：代理廣度不計分（L0）\n'
                                        'from shared.station_specs import is_invalid_number\n',
                                        'from shared.inst_net import is_net_observed  # 批 Z33：外資淨額未觀測（L1 '
                                        '預填／L3 補零推出）不當真值\n'
                                        'from shared.station_specs import is_invalid_number\n'),
                                       ('        _jq = _get(_jq_info, "avg")      # 沒有 avg ⇒ None（缺值），⛔ 不退回 '
                                        'warroom（可能是舊頁籤殘留）\n'
                                        '        # DEC-074 B（客戶 2026-10-23）：代理（估算）廣度不得計分 —— '
                                        '本列是健康分對帳（兩種演算法各算一次），\n'
                                        '        #   一樣是計分路徑 ⇒ 經 L0 `jingqi_for_scoring`：代理 ⇒ 缺值（⛔ 不退回 '
                                        'warroom，理由同上一行）。\n'
                                        '        if not jingqi_for_scoring(_jq_info):\n'
                                        '            _jq = None\n'
                                        '        # 📌 批 Z62（Z60 更正，上行註解保留）：Z60 起新 UI 也會寫 warroom，但其 '
                                        '`jingqi_avg` 是由\n',
                                        '        _jq = _get(_jq_info, "avg")      # 沒有 avg ⇒ None（缺值），⛔ 不退回 '
                                        'warroom（可能是舊頁籤殘留）\n'
                                        '        # 📌 批 Z62（Z60 更正，上行註解保留）：Z60 起新 UI 也會寫 warroom，但其 '
                                        '`jingqi_avg` 是由\n')),
 'src/ui/tabs/macro/handlers.py': (('            # 所以永遠不會「缺席」,只會靜默變成最強利空)。改為據實列出缺哪條腿。\n'
                                    '            # 📌 DEC-074 B（客戶 2026-10-23，有意識的修改，⛔ 不是漏刪）：旌旗（廣度）缺席自本批起\n'
                                    '            #   健康分 = None（⬜ 未評估），**不再**重新歸一 ⇒ 舊句「權重已重新歸一化」在該情形不屬實。\n'
                                    '            #   只改字（共用層 L2 契約改變的連帶文案；DEC-019 揭露），版面不動。\n'
                                    '            #   大盤評分缺席而旌旗真值在（D-3）仍是既有歸一 ⇒ 該情形維持原句。\n'
                                    "            _breadth_reason = tl.get('health_unavailable_reason') == "
                                    "'breadth'\n"
                                    "            if tl.get('health_partial'):\n",
                                    '            # 所以永遠不會「缺席」,只會靜默變成最強利空)。改為據實列出缺哪條腿。\n'
                                    "            if tl.get('health_partial'):\n"),
                                   ("                _leg_txt = '、'.join(_legs) if _legs else '部分分項'\n"
                                    "                if tl.get('health') is None:\n"
                                    "                    _msg += (f'\u3000🩺 **綜合健康度未評估：缺 {_leg_txt}**'\n"
                                    "                             '（依 DEC-074 不以其餘分項改權重補出分數，代理估算的廣度值不計分）。')\n"
                                    '                else:\n'
                                    "                    _msg += (f'\u3000🩺 **綜合健康度未含 "
                                    "{_leg_txt}**，本次僅由其餘分項'\n"
                                    "                             '推算（權重已重新歸一化，非補中性值/非補 0），'\n"
                                    "                             '請降低對該分數的信賴。')\n"
                                    "            _msg += '\u3000建議按「🚀 一鍵更新全部數據」後再操作。'\n"
                                    '            if _breadth_reason:\n'
                                    "                _msg += '（市場廣度那一項缺的是正式資料來源，更新資料不會改變。）'\n"
                                    '            st.warning(_msg)\n',
                                    "                _leg_txt = '、'.join(_legs) if _legs else '部分分項'\n"
                                    "                _msg += (f'\u3000🩺 **綜合健康度未含 {_leg_txt}**，本次僅由其餘分項'\n"
                                    "                         '推算（權重已重新歸一化，非補中性值/非補 0），'\n"
                                    "                         '請降低對該分數的信賴。')\n"
                                    "            _msg += '\u3000建議按「🚀 一鍵更新全部數據」後再操作。'\n"
                                    '            st.warning(_msg)\n')),
 'src/ui/tabs/macro/section_short.py': (("                #  `source != 'ADL'` 時標「⚠️ 代理值」）。\n"
                                         '                # ~~刻意**不新增** is_proxy 鍵：jingqi_info 的 7 鍵契約由\n'
                                         '                # tests/test_review_fixes_v19_84.py:19 '
                                         '釘住，provenance 用既有\n'
                                         '                # `source` 字串承載即可，不必為單一寫入站擴充契約（§8.1 step 6）。~~\n'
                                         '                # 📌 DEC-074 B（客戶 2026-10-23，有意識的修改，⛔ 不是漏刪）：契約自本批起 '
                                         '8 鍵\n'
                                         '                #   （L3 `jingqi_calc` 加 '
                                         '`is_proxy`）。本站寫的是**單日**上漲佔比、非正式口徑（5 日均）\n'
                                         '                #   ⇒ D-2（內部拍板）：同樣標 '
                                         '`is_proxy=True`、不計分。舊理由（不為單一寫入站擴充契約）\n'
                                         '                #   在契約已因 L3 擴充後不再成立；改這一行是因為它寫進**共用層**計分會讀的 '
                                         '`jingqi_info`\n'
                                         '                #   （DEC-019：新 UI 依賴的根因修正，非舊 UI 功能改動）。\n'
                                         "                if not st.session_state.get('jingqi_info'):\n",
                                         "                #  `source != 'ADL'` 時標「⚠️ 代理值」）。\n"
                                         '                # 刻意**不新增** is_proxy 鍵：jingqi_info 的 7 鍵契約由\n'
                                         '                # tests/test_review_fixes_v19_84.py:19 '
                                         '釘住，provenance 用既有\n'
                                         '                # `source` 字串承載即可，不必為單一寫入站擴充契約（§8.1 step 6）。\n'
                                         "                if not st.session_state.get('jingqi_info'):\n"),
                                        ("                        'total': 0,\n"
                                         "                        'is_proxy': True,   # DEC-074 B／D-2：非正式口徑 "
                                         '⇒ 不計分\n'
                                         '                    }\n',
                                         "                        'total': 0,\n                    }\n")),
 'src/ui/tabs/tab_macro_v2.py': (('from shared.macro_provenance import is_m1b_m2_proxy  # '
                                  'DL-f1-s17：代理值不計分（L0 SSOT）\n'
                                  'from shared.macro_provenance import (  # DEC-074 B：代理廣度只顯示不計分（L0 SSOT）\n'
                                  '    BREADTH_LAMP_KEYS, breadth_proxy_badge, is_breadth_proxy,\n'
                                  ')\n'
                                  'from src.compute.macro.macro_helpers import compute_five_bucket_summary\n',
                                  'from shared.macro_provenance import is_m1b_m2_proxy  # '
                                  'DL-f1-s17：代理值不計分（L0 SSOT）\n'
                                  'from src.compute.macro.macro_helpers import '
                                  'compute_five_bucket_summary\n'),
                                 ('            band = classify_danger(None, spec)\n'
                                  '        # DEC-074 B（客戶 2026-10-23）：市場廣度兩盞（jingqi／adl）側車 `is_proxy`（L2 以 '
                                  'L0 判）\n'
                                  '        # → 同上：燈號走既有 gray，不進桶摘要／指標危險度；值與註記照樣顯示。\n'
                                  '        _breadth_proxy = spec.key in BREADTH_LAMP_KEYS and '
                                  'is_breadth_proxy(rec)\n'
                                  '        if _breadth_proxy:\n'
                                  '            band = classify_danger(None, spec)\n'
                                  '\n',
                                  '            band = classify_danger(None, spec)\n\n'),
                                 ('            value_note=(m1b_m2_proxy_badge(rec)\n'
                                  '                        if spec.key == "m1b_m2_gap" and has_value\n'
                                  '                        else (breadth_proxy_badge(rec) if _breadth_proxy '
                                  'and has_value else "")),\n'
                                  '        ))\n',
                                  '            value_note=(m1b_m2_proxy_badge(rec)\n'
                                  '                        if spec.key == "m1b_m2_gap" and has_value else '
                                  '""),\n'
                                  '        ))\n')),
 'src/ui/views/page_today.py': (('from shared.macro_provenance import M1B_PROXY_VALUE_NOTE\n'
                                 'from shared.macro_provenance import BREADTH_LAMP_KEYS, '
                                 'BREADTH_PROXY_VALUE_NOTE  # DEC-074 B\n'
                                 '# 燈卡「變化方向」列（2026-09-24）：哪幾盞燈有這一列 ＋ 列標籤。純常數 L0。\n',
                                 'from shared.macro_provenance import M1B_PROXY_VALUE_NOTE\n'
                                 '# 燈卡「變化方向」列（2026-09-24）：哪幾盞燈有這一列 ＋ 列標籤。純常數 L0。\n'),
                                ('\n'
                                 '#: (d) **重抓不會改變**：缺的是正式資料來源本身（DEC-074 B，客戶 2026-10-23）。\n'
                                 '#: 市場位階／建議持股契約因「缺真實市場廣度（漲跌家數）」而未評估時專用 —— 本頁按鈕會重抓\n'
                                 '#: 代理（估算）家數，但代理值依 DEC-074 **不計分**，所以按幾次都一樣（計畫 I-4：不得暗示重跑就會有）。\n'
                                 '#: ⛔ 不得寫「重新抓取」「重新載入」之類的指引（`tests/test_dec074_breadth_gate.py` 守衛）。\n'
                                 'EXIT_WAIT_BREADTH_SOURCE: str = (\n'
                                 '    f"{NO_EXIT_MARKER} —— **這一格更新資料不會改變**：缺的是正式的市場廣度（漲跌家數）資料來源，"\n'
                                 '    "不是這一輪沒抓到；目前只有由加權指數推估的代理值，依客戶裁示（DEC-074）只顯示、不計分。"\n'
                                 '    "正式廣度資料接上之前，這一格會一直是未評估")\n'
                                 '\n'
                                 '#: 「缺真實市場廣度 ⇒ 未評估」的 why（卡① / 卡③ / 狀態列「總經」／三欄摘要「位階」共用一句）。\n'
                                 'BREADTH_UNEVALUATED_WHY: str = (\n'
                                 '    "總經健康分需要真實市場廣度（漲跌家數），目前只有加權指數推估的代理值，"\n'
                                 '    "依 DEC-074 不計分 ⇒ 健康分未評估；依 DEC-075 市場位階也一併未評估，"\n'
                                 '    "**不改用另一套規則引擎補出位階**，本站也不以缺值推導一個安全水位")\n'
                                 '\n'
                                 '\n'
                                 'def regime_breadth_unevaluated(regime: Mapping[str, Any] | None) -> bool:\n'
                                 '    """L3 總經契約是不是「因缺真實市場廣度而未評估」（`source == SOURCE_UNEVALUATED_BREADTH`）。\n'
                                 '\n'
                                 '    讀的是契約自己的 `source` 旗標（上游帶下來的），本頁不拿資料反推（`shared/ui_state.py` 鐵律）。\n'
                                 '    """\n'
                                 '    if not isinstance(regime, Mapping):\n'
                                 '        return False\n'
                                 '    from shared import regime_arbiter as _RA_b\n'
                                 '    return regime.get("source") == _RA_b.SOURCE_UNEVALUATED_BREADTH\n'
                                 '\n'
                                 '\n'
                                 '#: (a)+(c) **複合**：一半可以在本頁重抓、一半摸不到。今日關鍵橫幅專用。\n',
                                 '\n#: (a)+(c) **複合**：一半可以在本頁重抓、一半摸不到。今日關鍵橫幅專用。\n'),
                                ('\n'
                                 'def contract_exit_retargeted(card: Card, regime: Mapping[str, Any] | None '
                                 '= None) -> Card:\n'
                                 '    """對面 `tab_today` 總經契約那幾格的出口，換成本頁現在真的成立的那一句。\n',
                                 '\n'
                                 'def contract_exit_retargeted(card: Card) -> Card:\n'
                                 '    """對面 `tab_today` 總經契約那幾格的出口，換成本頁現在真的成立的那一句。\n'),
                                ('    `now` 不動；`tab_today.py` 照舊一個字都不動。\n'
                                 '\n'
                                 '    📌 **DEC-074 B／DEC-075 D-1(a)（2026-10-23）：`regime=`（選填，預設 None ⇒ '
                                 '與修前逐一相同）。**\n'
                                 '    契約 `source == SOURCE_UNEVALUATED_BREADTH`（缺真實市場廣度 ⇒ 未評估）時，換成\n'
                                 '    `EXIT_WAIT_BREADTH_SOURCE` ＋ `BREADTH_UNEVALUATED_WHY` —— '
                                 '對面的「四條來源本輪皆無值」與\n'
                                 '    本頁的「按一次就會重抓」在這一態**都不屬實**（重抓不會讓代理值變成可計分）。\n'
                                 '    """\n',
                                 '    `now` 不動；`tab_today.py` 照舊一個字都不動。\n    """\n'),
                                ('    _note = card.note\n'
                                 '    if _note.where is CONTRACT_NO_EXIT_WHERE and '
                                 'regime_breadth_unevaluated(regime):\n'
                                 '        _note = dc_replace(_note, where=EXIT_WAIT_BREADTH_SOURCE, '
                                 'why=BREADTH_UNEVALUATED_WHY)\n'
                                 '        return dc_replace(card, note=_note)\n'
                                 '    if _note.where is CONTRACT_NO_EXIT_WHERE:\n',
                                 '    _note = card.note\n    if _note.where is CONTRACT_NO_EXIT_WHERE:\n'),
                                ('        _band = classify_danger(None, _spec)\n'
                                 '    # DEC-074 B（客戶 2026-10-23）：市場廣度兩盞（jingqi／adl）同一處置 —— 側車 `is_proxy`\n'
                                 '    # （L2 以 L0 判）→ 燈號走既有 gray（不判燈級）；現值＋代理註記照樣顯示。\n'
                                 '    if key in BREADTH_LAMP_KEYS and rec.get("is_proxy") is True:\n'
                                 '        _band = classify_danger(None, _spec)\n'
                                 '\n',
                                 '        _band = classify_danger(None, _spec)\n\n'),
                                ('        _shown = f"{_shown}{M1B_PROXY_VALUE_NOTE}"\n'
                                 '    if key in BREADTH_LAMP_KEYS and _shown and rec.get("is_proxy") is '
                                 'True:   # DEC-074 B\n'
                                 '        _shown = f"{_shown}{BREADTH_PROXY_VALUE_NOTE}"\n'
                                 '\n',
                                 '        _shown = f"{_shown}{M1B_PROXY_VALUE_NOTE}"\n\n'),
                                ('        return _head + "建議持股需要總經健康分算出姿態帶，本輪沒有取得" + _tail\n'
                                 '    if regime_breadth_unevaluated(regime):\n'
                                 '        # DEC-074 B：原因是缺真實市場廣度（代理不計分），⛔ 不寫成「本輪沒有值」（那暗示重抓會有）。\n'
                                 '        return _head + BREADTH_UNEVALUATED_WHY\n'
                                 '    _parts: list[str] = []\n',
                                 '        return _head + "建議持股需要總經健康分算出姿態帶，本輪沒有取得" + _tail\n'
                                 '    _parts: list[str] = []\n'),
                                ('            note=Note(now="**今天能不能出手：尚未評估**", why=_why,\n'
                                 '                      # DEC-074 B（SHOULD-A2）：以**原因**判出口 —— 缺真實廣度 ⇒ '
                                 '重抓不會改變；\n'
                                 '                      #   其餘未評估（含 F1 三源全敗）照舊 `EXIT_RETRY_HERE`。\n'
                                 '                      where=(EXIT_FIX_CODE if alloc_error\n'
                                 '                             else (EXIT_WAIT_BREADTH_SOURCE\n'
                                 '                                   if (_att_fail is None and '
                                 'regime_breadth_unevaluated(regime))\n'
                                 '                                   else EXIT_RETRY_HERE))))))\n'
                                 '\n',
                                 '            note=Note(now="**今天能不能出手：尚未評估**", why=_why,\n'
                                 '                      where=(EXIT_FIX_CODE if alloc_error\n'
                                 '                             else EXIT_RETRY_HERE)))))\n'
                                 '\n'),
                                ('                     macro_attempt_failed_why(_att_fail) if _att_fail is '
                                 'not None else\n'
                                 '                     # DEC-075 D-1(a)：缺真實廣度 ⇒ 位階一併未評估（⛔ 不是「四條來源皆無值」）。\n'
                                 '                     BREADTH_UNEVALUATED_WHY if '
                                 'regime_breadth_unevaluated(regime) else\n'
                                 '                     "L3 canonical 契約四條來源本輪皆無值 → 回 `unknown`，"\n',
                                 '                     macro_attempt_failed_why(_att_fail) if _att_fail is '
                                 'not None else\n'
                                 '                     "L3 canonical 契約四條來源本輪皆無值 → 回 `unknown`，"\n'),
                                ('                #    離開未評估 ⇒ 改走 `EXIT_RETRY_HERE`（理由同卡①）。錯誤分支未動。\n'
                                 '                where=(EXIT_FIX_CODE if regime_error\n'
                                 '                       else (EXIT_WAIT_BREADTH_SOURCE\n'
                                 '                             if (_att_fail is None and '
                                 'regime_breadth_unevaluated(regime))\n'
                                 '                             else EXIT_RETRY_HERE)))),\n'
                                 '            facts=((REGIME_SCOPE_FACT_KEY, REGIME_SCOPE_NOTE),)))\n',
                                 '                #    離開未評估 ⇒ 改走 `EXIT_RETRY_HERE`（理由同卡①）。錯誤分支未動。\n'
                                 '                where=(EXIT_RETRY_HERE if not regime_error\n'
                                 '                       else EXIT_FIX_CODE))),\n'
                                 '            facts=((REGIME_SCOPE_FACT_KEY, REGIME_SCOPE_NOTE),)))\n'),
                                ('    (EXIT_FIX_CODE,               "需修程式"),\n'
                                 '    (EXIT_WAIT_BREADTH_SOURCE,    "等正式廣度資料來源"),   # DEC-074 B\n'
                                 '    (EXIT_ALERTS_PARTIAL,         "只更新得到一半"),\n',
                                 '    (EXIT_FIX_CODE,               "需修程式"),\n'
                                 '    (EXIT_ALERTS_PARTIAL,         "只更新得到一半"),\n'),
                                ('                        band_zh_color: Mapping[str, tuple[str, str]] | '
                                 'None = None,\n'
                                 '                        l4_error: str = "",\n'
                                 '                        regime: Mapping[str, Any] | None = None) -> '
                                 'tuple[Tile, ...]:\n'
                                 '    """葉1 ③ 三欄摘要 → `Tile`。**只換「風險」那一格，其餘照 `_tiles_of_cards()`。**\n',
                                 '                        band_zh_color: Mapping[str, tuple[str, str]] | '
                                 'None = None,\n'
                                 '                        l4_error: str = "") -> tuple[Tile, ...]:\n'
                                 '    """葉1 ③ 三欄摘要 → `Tile`。**只換「風險」那一格，其餘照 `_tiles_of_cards()`。**\n'),
                                ('                      band_zh_color=band_zh_color, l4_error=l4_error)\n'
                                 '         if _c.key == SUMMARY_RISK_KEY else '
                                 'Tile(contract_exit_retargeted(_c, regime)))\n'
                                 '        for _c in cards)\n',
                                 '                      band_zh_color=band_zh_color, l4_error=l4_error)\n'
                                 '         if _c.key == SUMMARY_RISK_KEY else '
                                 'Tile(contract_exit_retargeted(_c)))\n'
                                 '        for _c in cards)\n'),
                                ('        _tiles_of_cards(status_bar_cards_with_sheet(\n'
                                 '            tuple(contract_exit_retargeted(_c, _regime) for _c in '
                                 '_bar_cards),\n'
                                 '            build_sheet_binding_card(_sheet_state, error=_sheet_err))),\n',
                                 '        _tiles_of_cards(status_bar_cards_with_sheet(\n'
                                 '            tuple(contract_exit_retargeted(_c) for _c in _bar_cards),\n'
                                 '            build_sheet_binding_card(_sheet_state, error=_sheet_err))),\n'),
                                ('            danger_requested=_readout.requested, '
                                 'danger_source=_danger_src,\n'
                                 '            band_zh_color=_band_zh, l4_error=_l4_err, regime=_regime))\n'
                                 '\n',
                                 '            danger_requested=_readout.requested, '
                                 'danger_source=_danger_src,\n'
                                 '            band_zh_color=_band_zh, l4_error=_l4_err))\n'
                                 '\n'))}


#: 本批 schema-additive 新增的鍵：`get_market_assessment` 的 `ma200_status`（`DH-TWII-MA200`）、
#: `calc_traffic_light` 的 `health_unavailable_reason`（DEC-074 B，D-4）。
DEC074_NEW_KEYS: tuple = ("ma200_status", "health_unavailable_reason")


def dec074_strip_new_keys(x):
    """舊批次 golden（整份 dict 的雜湊）比對用：拿掉本批新增、**且值為 None** 的鍵，其餘原樣。非 dict 原樣回傳。

    ⚠️ 值不是 None（＝本批的新行為真的生效：年線未評估、健康分因缺廣度未評估）⇒ **不拿掉**，
    golden 照樣會紅 —— 那是行為變更，必須在該測試據實處理，不在這裡洗掉。
    """
    if isinstance(x, dict) and any(k in x and x[k] is None for k in DEC074_NEW_KEYS):
        return {k: v for k, v in x.items() if not (k in DEC074_NEW_KEYS and v is None)}
    return x


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def dec074_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批（DEC-074/075）之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = DEC074_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        # 已被前一個掛點換回（每一組的 `新寫法` 都跨在本批改動的邊界上，換回後必然 0 次）。
        # ⚠️ 不再檢查 `舊寫法` 在不在：更舊的批次可能已改寫它的上下文（例：z62 改 ma200 鄰行）。
        return code
    assert all(c == 1 for c in counts), (
        f"{rel} 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new[:120]!r}"
        code = code.replace(new, old)
    return code


def test_dec074_revert_is_exact_base_source():
    for rel in sorted(DEC074_REVERT_PAIRS):
        code = dec074_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == DEC074_BASE_SHA[rel], rel


def test_dec074_revert_is_idempotent():
    """同一份碼經過兩個掛點：第二次必須原樣（不換第二次、不炸）。"""
    for rel in sorted(DEC074_REVERT_PAIRS):
        once = dec074_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert dec074_revert_for(rel, once) == once, rel
