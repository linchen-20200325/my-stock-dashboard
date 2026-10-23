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

DEC074_BASE_SHA = {'shared/allocation_decision.py': '8945f0074f64d59f84f7e9bde268baada44a770a79698642ae66e2c7b7977284',
 'shared/macro_buckets.py': 'cd9fc1d07b7195fe0b58ce528f97490b6364bebd9ba2dccab86c063bea818b10',
 'shared/macro_forward_test_schema.py': '2c50db57f68367b2d4580e8c6e292d377f5ef99c59fd958082c755ed55b0c93c',
 'shared/macro_provenance.py': 'b780bb3cd655ce0c7d9ccbfb6ebcbc1051ca1f35bff133f486f720d895329c83',
 'shared/regime_arbiter.py': 'a5a7a81386c4e5a36efac69483eba665edbabbd611f0475b6fa398ad9cc3b4fb',
 'shared/scoring_regime_gate.py': '1e928beb081d2dc8f5a7e77f509dd4d3b26e31b423802230dd8225d0b1c916b1',
 'shared/signal_thresholds.py': '9f629902b72a584cefe6956ca72b50e389d7d695c97c825c0d415831275c3656',
 'src/compute/macro/macro_forward_test.py': 'befdcd0b35f680cd2f863bb1f47273208e1e9213273cf2c0f7421f417b3410de',
 'src/compute/macro/macro_helpers.py': '10e42e7d4773a3944aaf1484ae87e456c5b305f0fe36fc7f773e0dc7ee139767',
 'src/data/core/data_registry.py': 'b1dd53605cc447b80e11249d39603ddc9950c5806da5b3528c5adb70d713eb59',
 'src/services/ai_qa_service.py': 'a0cbf6a099a602026a017060cd734c3f871004984af37bfa5cbfc6480a03ec2d',
 'src/services/allocation_service.py': '018809fb170abf3c1e2b29c654a18367b59600e86151bff79865165e77d9eb2e',
 'src/services/dividend_station_service.py': 'f9f8464d7906310830c2c80f15d9c942530b8451347981d2b2197582e98bb798',
 'src/services/jingqi_calc.py': '9443980c4b15de033d8645e2d77d3990c7782913c1881a145f218b6212a1bca9',
 'src/services/macro_fetch_orchestrator.py': '9171a8a4fe9312e4e7680a7b8c5dce308433ee297692098125a5b8e5b9871838',
 'src/services/macro_refresh_service.py': 'f1606dec90304bf3895caa14e5bd4b73387042c962d6418b96a0a8b50474b955',
 'src/services/macro_state_locker.py': 'f43e7c20b9c03f1c03a3452308728309d350f4015b948ab40c1df7caf02dc1a3',
 'src/services/macro_v2_service.py': '154968adfad5763837719eb97e2cf3cf2f3342f4fc58b0de152dc71647b446b3',
 'src/services/market_assessment_apply.py': 'b9ed911a03531dc9a6dddb33f405d79bac92f9cefe8f3fab53cd4b5d64128ed7',
 'src/services/market_strategy.py': 'ade4b3a9b729aba1589669dd0e85f9c10b4ee0a8d1bcbbe6820ba25265e97c89',
 'src/services/reconcile_service.py': 'd4390625de6c44a1eef7b14654faf4df9cd13dd526dd07908b8aaa52e3a4a3c1',
 'src/services/section_inputs.py': '7c0c9b1abdbccd570e01bab93fbe18111790873b96b58f6c422db4d02cdbcede',
 'src/ui/pages/reconcile_panel.py': '64d79b74318a1db7aefd3427fd173d3d4998f0cb2e6145bd8a2e4e1667c5b8a8',
 'src/ui/render/macro_v2_cards.py': 'ef9fda3152fd1547358f9c38bddfd7aadb73e392d5d4a63b441803ac1c7e7436',
 'src/ui/tabs/macro/handlers.py': 'e23c5556742986c0b6ac5c7fe3e50c5d6ab3ad0514daa0258c4996024be4d9c1',
 'src/ui/tabs/macro/section_short.py': '1cb052c72acc6650b0bcff60ebbe65e8be4395950712e5c6d39ddf891c2a79d1',
 'src/ui/tabs/tab_edu.py': 'eb46d59e4273ea3f20073dcbb30009432bd9835e1dfb35e3d02593f8fb1db020',
 'src/ui/tabs/tab_macro_v2.py': 'cb34f1720781f5f7d55e484becebcedfd65adafc4eec0454773cafa0bf9f1617',
 'src/ui/views/page_hold.py': 'bc85ebb41b2c392199c32a95f2a7a0f21d5ea0569024d9546ad0e547eeb69b53',
 'src/ui/views/page_today.py': '672697ff9437a9c624840d35e6098a6d8484417ed6a9be462f7d89fcc4be37ac'}

DEC074_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'shared/allocation_decision.py': (('    risk_cap_disclosure: Any = None\n'
                                    "    #: DEC-075 回修（MUST-2，2026-10-23）：未評估的**原因**。'breadth' ＝ 缺真實市場廣度（契約\n"
                                    "    #: `source == SOURCE_UNEVALUATED_BREADTH`）；'' ＝ 其他原因或已評估。最後一欄、有預設 ⇒ "
                                    '既有建構不用改。\n'
                                    "    unevaluated_reason: str = ''\n"
                                    '\n',
                                    '    risk_cap_disclosure: Any = None\n\n'),
                                   ('        """一句話結論：\'🟠 轉守 → 建議持股 30–50%\'。"""\n'
                                    '        if not self.is_loaded and self.unevaluated_reason == '
                                    "'breadth':\n"
                                    '            # DEC-075 回修：缺真實廣度 ⇒ 更新不會改變（⛔ 不叫人重抓；I-4）。其餘原因照舊。\n'
                                    "            return '⬜ 總經未評估 — 缺真實市場廣度（DEC-074），更新資料不會改變'\n"
                                    '        if not self.is_loaded:\n',
                                    '        """一句話結論：\'🟠 轉守 → 建議持股 30–50%\'。"""\n'
                                    '        if not self.is_loaded:\n'),
                                   ('    if not _is_loaded or _health is None:\n'
                                    '        # DEC-075 回修（QA1 MUST-2）：原因是缺真實廣度時，~~「warroom_summary / '
                                    'macro_state.json 皆無有效值」~~\n'
                                    '        #   不屬實（warroom 在、檔案也可能有效，只是 DEC-075 (a) 不採用）⇒ '
                                    '換成屬實的那句；其餘原因逐字照舊。\n'
                                    '        from shared.regime_arbiter import UNEVALUATED_BREADTH_EXPLAIN, '
                                    'is_breadth_unevaluated\n'
                                    '        _breadth = is_breadth_unevaluated(_ms)\n'
                                    '        return AllocationDecision(\n',
                                    '    if not _is_loaded or _health is None:\n'
                                    '        return AllocationDecision(\n'),
                                   ("            cap_pct=None, cap_name='', caps=tuple(caps),\n"
                                    '            drivers=((UNEVALUATED_BREADTH_EXPLAIN,) if _breadth else\n'
                                    "                     ('總經尚未評估（warroom_summary / macro_state.json "
                                    "皆無有效值）',)),\n"
                                    '            conflicts=tuple(conflicts),\n'
                                    "            unevaluated_reason=('breadth' if _breadth else ''),\n"
                                    '        )\n',
                                    "            cap_pct=None, cap_name='', caps=tuple(caps),\n"
                                    "            drivers=('總經尚未評估（warroom_summary / macro_state.json "
                                    "皆無有效值）',),\n"
                                    '            conflicts=tuple(conflicts),\n'
                                    '        )\n')),
 'shared/macro_buckets.py': (('               note="≥3.5% 外資提款風險 / ≥4% 通膨嚴峻", source=f"黃線 '
                              '{_CPI_YELLOW:g}%／紅線 {_CPI_RED:g}%：有既有常數背書（統一閾值表）"),\n'
                              "    # DH-EXPORT-LABEL（DEC-075 批 1'，客戶 2026-10-23「台灣出口燈依實際資料內容修正名稱」；修正錯誤，\n"
                              '    #   有意識的更正，⛔ 不是漏刪）：~~"台灣出口訂單 YoY"~~ —— 實際取值是**財政部海關出口金額年增率**\n'
                              '    #   （`macro_snapshot.fetch_export_block`；五桶 `_traced("tw_export", '
                              '"財政部海關出口金額年增率…")`），\n'
                              '    #   不是經濟部外銷訂單。只改名稱，⛔ 不換來源、⛔ 不改門檻與計算（v19.85／v19.183 他處已同樣正名）。\n'
                              '    DangerSpec("tw_export", "台灣出口金額 YoY（海關）", "mid", "%", "low_bad",\n'
                              '               yellow=0.0, red=-5.0, decimals=1,\n',
                              '               note="≥3.5% 外資提款風險 / ≥4% 通膨嚴峻", source=f"黃線 '
                              '{_CPI_YELLOW:g}%／紅線 {_CPI_RED:g}%：有既有常數背書（統一閾值表）"),\n'
                              '    DangerSpec("tw_export", "台灣出口訂單 YoY", "mid", "%", "low_bad",\n'
                              '               yellow=0.0, red=-5.0, decimals=1,\n'),),
 'shared/macro_forward_test_schema.py': (('#: (1→2),不是規則改版(2026-10-15 總管裁定:hash 演算法不改,在此註明)。\n'
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
                                 '# ~~為什麼 `jingqi_info` 只認**明確布林旗標**、不做 source 字串比對：…沒有旗標的 dict … 沿用既有語意 = '
                                 '真值~~\n'
                                 '# 📌 DEC-075 批 A 回修（QA1 S-6，2026-10-23，有意識的修改，⛔ 不是漏刪）：失敗方向改為與 DataFrame '
                                 '路徑一致的\n'
                                 '#   **fail-safe** —— `jingqi_info`（或 readiness 側車一筆 record）**只有** '
                                 '`is_proxy` 是明確的布林 False\n'
                                 '#   （Python `False` 或 '
                                 '`numpy.bool_(False)`）才算真值；`True`、`np.bool_(True)`、字串、None、**缺旗標**一律視同代理。\n'
                                 '#   舊理由（「拿不到旗標時不宣稱它是代理值」，M1B 同一分寸）在廣度上被權衡掉：本 repo 目前**沒有任何**\n'
                                 '#   真實漲跌家數來源，沒標旗標的數字只可能來自估算；漏標時當真值計分＝DEC-074 明禁的那件事。\n'
                                 '#   producer（`jingqi_calc`、舊 UI `section_short`、`section_inputs` 由 warroom '
                                 '合成的 fallback）一律寫旗標。\n'
                                 '# ⚠️ 上游 **DataFrame**（`fetch_adl` 的回傳）同樣：缺 `is_proxy` 欄一律視同代理（見 '
                                 '`adl_df_is_proxy`）。\n'
                                 '\n'
                                 '#: 代理廣度值貼在數字後面的短註記（顯示用；判燈／計分一律不讀）。\n'
                                 "BREADTH_PROXY_VALUE_NOTE: str = '（代理估算值，不計分）'\n"
                                 '\n'
                                 '#: 受本判定管轄的五桶燈 key（`shared.macro_buckets.BUCKET_DANGER_SPECS` 的 key）。\n'
                                 "BREADTH_LAMP_KEYS: frozenset = frozenset({'jingqi', 'adl'})\n"
                                 '\n'
                                 '\n'
                                 'def _is_explicit_false(v) -> bool:\n'
                                 '    """明確的布林 False（Python `False` 或 `numpy.bool_(False)`）；其餘（含 '
                                 '0、\'False\'、None）一律否。L0 不 import numpy。"""\n'
                                 '    if v is False:\n'
                                 '        return True\n'
                                 "    return type(v).__name__ in ('bool_', 'bool') and type(v).__module__ == "
                                 "'numpy' and not bool(v)\n"
                                 '\n'
                                 '\n'
                                 'def is_breadth_proxy(info: Optional[dict]) -> bool:\n'
                                 '    """`jingqi_info`（或五桶 readiness 側車的一筆 '
                                 'record）是不是代理（估算）廣度？**fail-safe**。\n'
                                 '\n'
                                 '    只有 `is_proxy` 為明確布林 False 才回 False（＝真值）；其餘一律 True（見上方說明）。\n'
                                 '    `info` 為 None / 非 dict → True（沒有可宣稱為真值的東西；呼叫端本來就走缺值路徑）。\n'
                                 '    """\n'
                                 '    if not isinstance(info, dict):\n'
                                 '        return True\n'
                                 "    return not _is_explicit_false(info.get('is_proxy'))\n"
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
                                 '    return not all(_is_explicit_false(_v) for _v in _tail)\n'
                                 '\n'
                                 '\n'
                                 'def breadth_proxy_held_back(jingqi_info: Optional[dict], adl_df) -> '
                                 'Optional[bool]:\n'
                                 '    """「缺真實市場廣度 ⇒ 未評估」那一態裡，本輪紅綠燈的輸入**有沒有一個被擋下的代理（估算）廣度值**？\n'
                                 '\n'
                                 '    QA-4 S-1（2026-10-23）：新 UI 的廣度未評估文案原本一律寫「目前只有由加權指數推估的代理值」——\n'
                                 '    ^TWII 全滅（ADL 與旌旗備援兩個代理都源自 ^TWII）時連代理值也沒有，那句不屬實。\n'
                                 '    本函式只回答「有沒有」，供文案二選一；**判燈／計分一律不讀**（純顯示用的訊號）。\n'
                                 '\n'
                                 '    輸入 ＝ 紅綠燈當輪吃的那兩份（`section_inputs.load_section_inputs(...)` 的 '
                                 '`jingqi_info` 與\n'
                                 "    `cl_data['adl']`），判定與 `calc_traffic_light` 的 `_jq_proxy_dropped` "
                                 '同口徑（旌旗有有限數值、\n'
                                 '    但經 `jingqi_for_scoring` 被擋下），另加 ADL：有列、且末列為代理、且計分開關關閉。\n'
                                 '\n'
                                 '    Returns:\n'
                                 '        True  ⇒ 至少一個代理值在、被擋下不計分（「目前只有代理值」屬實）；\n'
                                 '        False ⇒ 旌旗沒有數值、ADL 也沒有任何列（「這一輪連代理值也沒有」屬實）；\n'
                                 '        None  ⇒ 拿不準（例：ADL 有列但末列不是代理）—— 呼叫端用兩種情境都屬實的中性句（⛔ 不猜）。\n'
                                 '    """\n'
                                 '    import math as _m\n'
                                 '    from shared.signal_thresholds import BREADTH_PROXY_SCORING_ENABLED\n'
                                 "    _avg = jingqi_info.get('avg') if isinstance(jingqi_info, dict) else "
                                 'None\n'
                                 '    try:\n'
                                 '        _jq_has = (_avg is not None and not isinstance(_avg, bool) and '
                                 '_m.isfinite(float(_avg)))\n'
                                 '    except (TypeError, ValueError):\n'
                                 '        _jq_has = False\n'
                                 '    if _jq_has and jingqi_for_scoring(jingqi_info) is None:\n'
                                 '        return True\n'
                                 '    try:\n'
                                 '        _adl_rows = 0 if adl_df is None else len(adl_df)\n'
                                 '    except Exception:  # noqa: BLE001 — 量不出列數 = 拿不準（⛔ 不猜成「沒有」）\n'
                                 '        return None\n'
                                 '    if _adl_rows > 0 and adl_df_is_proxy(adl_df) and not '
                                 'BREADTH_PROXY_SCORING_ENABLED:\n'
                                 '        return True\n'
                                 '    if not _jq_has and _adl_rows == 0:\n'
                                 '        return False\n'
                                 '    return None\n',
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
                               '#: 「缺真實市場廣度 ⇒ 總經未評估」的對外說明（持股頁、AI 問答、姿態帶 drivers 共用一句；DEC-075 回修 MUST-2）。\n'
                               '#: ⛔ 不得寫「重新抓取」「重新載入」「一鍵更新」之類的指引（I-4：重跑不會讓代理值變成可計分）；\n'
                               '#: ⛔ 不得寫「macro_state.json 無快照」（breadth 情境下檔案可能有效，只是 DEC-075 (a) 不採用它）。\n'
                               '#: 📌 QA-4 S-1（2026-10-23，有意識的修改，⛔ 不是漏刪；決策者 AI 總管）：~~「目前只有由加權指數推估的代理值」~~ ——\n'
                               '#:   DEC-075 D-1(a) 回修（QA3 MUST-R1）起本句也用在 ^TWII 全滅（連代理值也沒有）那一態，該半句在那一態不屬實。\n'
                               '#:   本常數改為**兩種情境都屬實的中性句**（拿不到區分訊號的讀點用，例：`allocation_decision` 的 drivers）；\n'
                               '#:   拿得到訊號的讀點改走 `unevaluated_breadth_explain(proxy_held_back)` '
                               '二選一。結論句（更新資料不會改變）不變。\n'
                               '_UNEVALUATED_BREADTH_TAIL: str = (\n'
                               "    '健康分因此算不出來；'\n"
                               "    '市場位階依 DEC-075 一併未評估，不改用另一套規則引擎補出位階。'\n"
                               "    '更新資料不會改變這個狀態，要等正式的廣度資料來源接上')\n"
                               'UNEVALUATED_BREADTH_EXPLAIN: str = (\n'
                               "    '總經未評估：缺真實市場廣度（漲跌家數）—— 由加權指數推估的代理值即使取得，'\n"
                               "    '依客戶裁示（DEC-074）也只顯示、不計分，' + _UNEVALUATED_BREADTH_TAIL)\n"
                               '#: '
                               '本輪**有**代理（估算）廣度值、被擋下不計分時（`shared.macro_provenance.breadth_proxy_held_back` 為 '
                               'True）。\n'
                               'UNEVALUATED_BREADTH_EXPLAIN_PROXY_HELD: str = (\n'
                               "    '總經未評估：缺真實市場廣度（漲跌家數）—— 目前只有由加權指數推估的代理值，'\n"
                               "    '依客戶裁示（DEC-074）只顯示、不計分，' + _UNEVALUATED_BREADTH_TAIL)\n"
                               '#: 本輪連代理值也沒有時（`breadth_proxy_held_back` 為 False；例：^TWII 全滅）。\n'
                               'UNEVALUATED_BREADTH_EXPLAIN_NO_PROXY: str = (\n'
                               "    '總經未評估：缺真實市場廣度（漲跌家數）—— 這一輪紅綠燈的輸入裡也沒有任何廣度資料'\n"
                               "    '（連由加權指數推估的代理值也沒有）；即使取得代理值，依客戶裁示（DEC-074）也只顯示、不計分，'\n"
                               '    + _UNEVALUATED_BREADTH_TAIL)\n'
                               '\n'
                               '\n'
                               'def unevaluated_breadth_explain(proxy_held_back: Optional[bool] = None) -> '
                               'str:\n'
                               '    """缺真實廣度 ⇒ 未評估的對外說明，依「本輪有沒有被擋下的代理值」二選一；None（拿不準）⇒ 中性句。"""\n'
                               '    if proxy_held_back is True:\n'
                               '        return UNEVALUATED_BREADTH_EXPLAIN_PROXY_HELD\n'
                               '    if proxy_held_back is False:\n'
                               '        return UNEVALUATED_BREADTH_EXPLAIN_NO_PROXY\n'
                               '    return UNEVALUATED_BREADTH_EXPLAIN\n'
                               '\n'
                               '\n'
                               'def is_breadth_unevaluated(state: Any) -> bool:\n'
                               '    """總經契約（`get_macro_state()` 的 dict）是不是「因缺真實市場廣度而未評估」。只看契約自己的 `source` '
                               '旗標。"""\n'
                               "    return isinstance(state, dict) and state.get('source') == "
                               'SOURCE_UNEVALUATED_BREADTH\n'
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
 'shared/scoring_regime_gate.py': (('    reason: str = ""\n'
                                    '    #: DEC-075 回修（MUST-2，2026-10-23）：拒絕評分的原因是「缺真實市場廣度」（契約 `source` '
                                    '旗標）。\n'
                                    '    #: 預設 False ⇒ 既有建構與輸出逐字不變。\n'
                                    '    breadth_unevaluated: bool = False\n'
                                    '\n',
                                    '    reason: str = ""\n\n'),
                                   ('            return ""\n'
                                    '        if self.breadth_unevaluated:\n'
                                    '            # DEC-075 回修：缺真實廣度 ⇒ ⛔ 不給「一鍵更新／重跑」救法（I-4）；其餘原因逐字照舊。\n'
                                    '            return (\n'
                                    '                f"⬜ 本批**不計算多因子總分**：{self.reason}。"\n'
                                    '                "多因子的 6 因子加權表（config.WEIGHT_TABLES）分 bull / neutral / '
                                    'bear "\n'
                                    '                "三態，總經沒有結論時任選一組都等於替你做一個大盤判斷（§1 寧可不給，"\n'
                                    '                "不給假的）。因此「多因子」欄一律標「⚪ 無法評分」、"\n'
                                    '                "「多因子評分排行」為空 —— **這不是 K 線抓取失敗**。"\n'
                                    '                "健康度／趨勢／357／出場訊號／型態目標價不吃 regime，全部照常顯示。"\n'
                                    '                "更新資料不會改變這個狀態：要等正式的市場廣度（漲跌家數）資料來源接上。"\n'
                                    '            )\n'
                                    '        return (\n',
                                    '            return ""\n        return (\n'),
                                   ('    if not macro_state.get("is_loaded"):\n'
                                    '        from shared.regime_arbiter import is_breadth_unevaluated\n'
                                    '        if is_breadth_unevaluated(macro_state):\n'
                                    '            # DEC-075 回修（MUST-2）：缺真實廣度 ⇒ 據實說原因（⛔ 不是「尚未算出」）。\n'
                                    '            return ScoringRegimeDecision(\n'
                                    '                None, "總經未評估（缺真實市場廣度，代理估算值依 DEC-074 不計分；位階依 DEC-075 '
                                    '一併未評估）",\n'
                                    '                breadth_unevaluated=True)\n'
                                    '        return ScoringRegimeDecision(None, "總經未評估（🌍 總經紅綠燈尚未算出結論）")\n',
                                    '    if not macro_state.get("is_loaded"):\n'
                                    '        return ScoringRegimeDecision(None, "總經未評估（🌍 總經紅綠燈尚未算出結論）")\n')),
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
                                  '\n'
                                  'MA200_WINDOW_DAYS: int = 200\n'
                                  '"""`market_strategy.get_market_assessment` 的 `ma200`（`market_score` '
                                  '年線項）所用的 rolling 視窗（交易日根數），\n'
                                  '同時是「算得出 ma200 所需的最少 K 棒數」。DEC-075 批 A（`DH-TWII-MA200`）把原 inline '
                                  '`rolling(200)`／\n'
                                  '`len(df_index) >= 200` 具名化；QA2 S-2 回修自 L3 下沉至此。**行為一位未動**（仍是 200）。\n'
                                  '\n'
                                  '⚠️ **與 `src/config/config.py` 的 `ANNUAL_MA = 240`（CLAUDE.md '
                                  '§3.3「年線」SSOT）是兩個不同口徑**：\n'
                                  '本常數是 `market_score` 歷史沿用的 200 日線（美股慣用的「200DMA 年線」說法），`ANNUAL_MA` 是 240 '
                                  '交易日的台股年線。\n'
                                  '⛔ 不得直接改成 `ANNUAL_MA`（那是行為變更，需另案校準）。`src/compute/etf/etf_calc.py`、\n'
                                  '`src/ui/render/etf_render.py` 兩處 inline `rolling(200)` 為 ETF '
                                  '另一條路徑，本批不動（另案收斂）。"""\n'
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
                                         'from shared.macro_provenance import adl_df_is_proxy as '
                                         '_adl_df_is_proxy  # noqa: E402\n'
                                         'from shared.signal_thresholds import (  # noqa: E402\n'
                                         '    BREADTH_PROXY_SCORING_ENABLED as '
                                         '_BREADTH_PROXY_SCORING_ENABLED,\n'
                                         ')\n'
                                         '\n'
                                         "#: ADL 只有代理（估算）家數時，`missing_sources` 那一項的說法（取代 'ADL 騰落指標'）。\n"
                                         "_ADL_PROXY_MISSING_TEXT = 'ADL "
                                         "騰落指標：由加權指數推估的代理家數，不算有效廣度來源（DEC-074）'\n"
                                         '\n'
                                         '#: `SOURCE_UNEVALUATED_BREADTH` 但本輪**沒有**任何廣度值（旌旗整包缺席）時的 '
                                         'action（取代文案表那一句）。\n'
                                         "_TL_ACTION_BREADTH_ABSENT = '⬜ 缺真實市場廣度（漲跌家數）—— 本輪也沒有取得任何廣度資料，健康分依 "
                                         "DEC-074 不以其餘分項補出'\n"
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
                                        ('    else:\n'
                                         '        # 回修 NIT-2：~~Method A 已權重歸一化~~ —— DEC-074 B 起旌旗缺席 Method A '
                                         '回 None（不歸一）；\n'
                                         '        #   只有大盤分缺席（D-3）才歸一。log 據實說。\n'
                                         "        print('[health_reconcile] skip:jqavg / 大盤評分 / health "
                                         "任一未取得'\n"
                                         "              '(Method A 此時為 None 或僅大盤分缺席的歸一值,Method B "
                                         "仍用固定預設),兩者不可比 → '\n"
                                         "              '本輪不對帳(§4.3)', file=sys.stderr)\n",
                                         '    else:\n'
                                         "        print('[health_reconcile] skip:jqavg / 大盤評分 / health "
                                         "任一未取得,'\n"
                                         "              'Method A 已權重歸一化而 Method B 仍用固定預設,兩者不可比 → '\n"
                                         "              '本輪不對帳(§4.3)', file=sys.stderr)\n"),
                                        ('    # 的 legacy 決策樹對拍測試)。\n'
                                         '    # DEC-074 B：health 算不出來「只因為缺廣度」（大盤評分本身在）⇒ 原因標 breadth\n'
                                         '    # （文案不再叫人重抓）。兩條腿都缺 ⇒ 既有 `SOURCE_UNLOADED`（其餘輸入也缺，重抓仍可能補上大盤分）。\n'
                                         '    # 📌 DEC-075 回修（QA1 MUST-1，2026-10-23，有意識的修改，⛔ 不是漏刪）：\n'
                                         '    #   ~~只在「大盤評分在」時才標 breadth~~ —— 舊理由「重抓仍可能補上大盤分」不成立：補上大盤分後健康分\n'
                                         '    #   仍是 None（廣度腿恆為代理）。若大盤分同時缺就標 UNLOADED，`get_macro_state` 會退回 '
                                         'macro_state.json\n'
                                         '    #   規則引擎位階（＝DEC-075 不採用的 (b)），出現「資料越少、結論越多」。\n'
                                         '    #   ⇒ 只要本輪**有代理廣度被擋下**（`_jq_proxy_dropped`）一律標 '
                                         'breadth（不看大盤分）；\n'
                                         '    #     旌旗整包缺席時維持舊規則（大盤分在 ⇒ breadth；兩條腿都缺、也沒有任何廣度輸入 ＝ F1 三源全空 ⇒ '
                                         'UNLOADED）。\n'
                                         '    _health_unavailable_reason = (\n'
                                         '        _RA.UNAVAILABLE_REASON_BREADTH\n'
                                         '        if (_health is None and _breadth_unavailable\n'
                                         '            and (_jq_proxy_dropped or _score_pct is not None)) '
                                         'else None)\n'
                                         '    _verdict = _RA.arbitrate_regime(\n',
                                         '    # 的 legacy 決策樹對拍測試)。\n    _verdict = _RA.arbitrate_regime(\n'),
                                        ('        health_defense_threshold=_h_thr, bull_min_score=_s_thr,\n'
                                         '        unavailable_reason=_health_unavailable_reason,\n'
                                         '    )\n',
                                         '        health_defense_threshold=_h_thr, bull_min_score=_s_thr,\n'
                                         '    )\n'),
                                        ('    _color, _label, _action, _sub = '
                                         '_TL_COPY_BY_SOURCE[_verdict.source]\n'
                                         '    if _verdict.source == _RA.SOURCE_UNEVALUATED_BREADTH and not '
                                         '_jq_proxy_dropped:\n'
                                         '        # 回修 NIT-1：本輪連代理值都沒有（旌旗整包缺席）⇒ 不說「代理估算值不計分」（那一輪沒有代理值）。\n'
                                         '        _action = _TL_ACTION_BREADTH_ABSENT\n'
                                         '    _icon = _verdict.light\n',
                                         '    _color, _label, _action, _sub = '
                                         '_TL_COPY_BY_SOURCE[_verdict.source]\n'
                                         '    _icon = _verdict.light\n'),
                                        ("        ('先行指標 (期貨/PCR/韭菜)',      bool(li_latest is not None and "
                                         "not li_latest.empty), 'li'),\n"
                                         '        # 回修 QA2 S-5（2026-10-23，有意識的修改，⛔ '
                                         "不是漏刪）：~~`bool(_cd.get('adl') is not None)`~~ ——\n"
                                         '        #   與上面旌旗同口徑：代理（估算）家數＝沒有有效的廣度來源（DEC-074 B），⛔ 不因「df '
                                         '在」就算有來源。\n'
                                         "        ('ADL 騰落指標',\n"
                                         "         bool(_cd.get('adl') is not None\n"
                                         '              and (_BREADTH_PROXY_SCORING_ENABLED or not '
                                         "_adl_df_is_proxy(_cd.get('adl')))), 'adl'),\n"
                                         '    ]\n',
                                         "        ('先行指標 (期貨/PCR/韭菜)',      bool(li_latest is not None and "
                                         "not li_latest.empty), 'li'),\n"
                                         "        ('ADL 騰落指標',                  bool(_cd.get('adl') is not "
                                         "None), 'adl'),\n"
                                         '    ]\n'),
                                        ('    #    凍結走**列名**這條路（畫面本來就會逐項印出 `missing_sources`）。\n'
                                         '    # DEC-074 B：旌旗**有代理值、被擋下不計分**時，缺失那一項據實寫原因（不是「沒抓到」）。\n'
                                         '    #   同一項替換、不另加一項 ⇒ 項數與 `conf` 一致。\n'
                                         '    if _jq_proxy_dropped:\n'
                                         '        _missing = [(_BREADTH_PROXY_MISSING_TEXT if _m == '
                                         '_CONF_LABEL_JINGQI else _m)\n'
                                         '                    for _m in _missing]\n'
                                         "    if _cd.get('adl') is not None and 'ADL 騰落指標' in _missing:\n"
                                         '        # 回修 S-5：ADL 有 df、只是代理 ⇒ 據實寫原因（同一項替換，項數與 conf 一致）。\n'
                                         "        _missing = [(_ADL_PROXY_MISSING_TEXT if _m == 'ADL 騰落指標' "
                                         'else _m) for _m in _missing]\n'
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
 'src/data/core/data_registry.py': ((')\n'
                                     '# ~~from shared.fred_series import FRED_NAPM~~ —— DEC-075 批 '
                                     "1'（2026-10-23）：EDU_GUIDE 的 NAPM 條目改名\n"
                                     "#   'TW_PMI'（見該處註解）後本檔已無讀者，依 pyflakes 一併拿掉（有意識的刪除，⛔ 不是漏刪）。\n"
                                     '\n',
                                     ')\nfrom shared.fred_series import FRED_NAPM\n\n'),
                                    ('        ],\n'
                                     "        # 回修 NIT-4（2026-10-23）：~~'ISM PMI（NAPM）'~~ —— 'NAPM' 教學條目已改名 "
                                     "'TW_PMI'（台灣 PMI），\n"
                                     '        #   本系統沒有美國 ISM 的教學卡；改列真的存在的那一張（只改字）。\n'
                                     "        'pair_with': ['台灣製造業 PMI（CIER）', '美債 10Y（^TNX）', "
                                     "'美元指數（DXY）'],\n"
                                     "        'historical_anchor': '2022 通膨高峰 6.6%（40 年新高）｜2008 雷曼 2.5%｜Fed "
                                     "目標 2.0%',\n",
                                     '        ],\n'
                                     "        'pair_with': ['ISM PMI（NAPM）', '美債 10Y（^TNX）', '美元指數（DXY）'],\n"
                                     "        'historical_anchor': '2022 通膨高峰 6.6%（40 年新高）｜2008 雷曼 2.5%｜Fed "
                                     "目標 2.0%',\n"),
                                    ('    },\n'
                                     "    # ── ISM 教學對映修正（DEC-075 批 1'，客戶 2026-10-23「修正 ISM "
                                     '教學對映」；修正錯誤，有意識的更正，\n'
                                     '    #    ⛔ '
                                     '不是漏刪）────────────────────────────────────────────────────────────────────\n'
                                     "    # ~~FRED_NAPM: {'meaning': 'ISM 製造業採購經理人指數…', 'pair_with': [...], "
                                     "'historical_anchor': '2008 雷曼跌至\n"
                                     "    #   33.1｜2020 疫情 41.5｜2021 復甦高點 63.7', 'upstream': …, "
                                     "'downstream': …}~~\n"
                                     '    # 這一篇唯一的顯示點是新 UI 總經 v2「台灣 '
                                     "PMI」燈（`macro_v2_service._EDU_KEY['ism_pmi']`）——\n"
                                     '    # 燈的值是**台灣 CIER PMI**（`VN1-MT-SSOT-ISM`），教學卻講美國 ISM '
                                     '與其歷史數字；`how_to_read` 早在\n'
                                     '    # 批 Z27 就已改吃台灣 PMI 門檻 token，只剩 '
                                     'meaning／pair_with／historical_anchor／upstream／downstream\n'
                                     "    # 是 ISM 文案。舊 UI 教學頁從未顯示它（key 'NAPM' 掛不上 registry ⇒ 孤兒，見\n"
                                     '    # `tests/test_b6a_edu_doc_parity.py::TestEduCardCountHonesty`）。\n'
                                     "    # ⇒ 改名為 'TW_PMI' 並把那五欄換成台灣 PMI 的事實（只用 repo "
                                     '內已有出處的敘述：`DATA_REGISTRY`\n'
                                     "    #   'cier-pmi' 列的 usage 原文）；`how_to_read` 一行未動（同一組 PMI token，⛔ "
                                     '不改門檻）。\n'
                                     '    #   ⛔ 不自擬台灣 PMI 歷史高低點數字（沒有可回溯出處，§1／§3.3）。\n'
                                     '    #   改名後美國 ISM 那一篇已無任何讀者（v3 §01-2：因本次改動才變成孤兒 ⇒ 本次收掉，不留第二份）。\n'
                                     "    #   ⚠️ key 刻意**不用** registry identifier 'cier-pmi'：用了會讓舊 UI "
                                     '教學頁多出一張卡（畫面結構變更，\n'
                                     "    #   須線框，DEC-003）；孤兒張數維持 2（'NAPM' → 'TW_PMI'），舊 UI 教學頁輸出逐字不變。\n"
                                     "    'TW_PMI': {\n"
                                     "        'meaning': '台灣製造業採購經理人指數（PMI），由中華經濟研究院（CIER）每月第一個工作日公布，'\n"
                                     "                   '是採購主管問卷彙總的台灣製造業景氣領先指標（>50 擴張、<50 收縮）。'\n"
                                     "                   '⚠️ 這不是美國 ISM 製造業指數。',\n"
                                     '        # F1 v19.184 §3.3：原本這 4 條是手打的 `50 / 50 / 50 / 45`。\n',
                                     '    },\n'
                                     '    FRED_NAPM: {\n'
                                     "        'meaning': 'ISM 製造業採購經理人指數，採購主管問卷彙總，領先 GDP 約 3–6 個月。',\n"
                                     '        # F1 v19.184 §3.3：原本這 4 條是手打的 `50 / 50 / 50 / 45`。\n'),
                                    ('        ],\n'
                                     "        'pair_with': ['台灣出口金額 YoY（海關）', '國發會景氣燈號', '費半 SOX'],\n"
                                     '        # 回修 NIT（2026-10-23）：~~「歷史高低點本系統尚未整理出可回溯的數字」~~ —— 與教學頁 PMI '
                                     '章節的\n'
                                     '        #   台灣 PMI 歷史表說法不一；改列 repo 內實際存在、可回溯的官方序列數字：\n'
                                     '        #   `data_cache/tw_pmi.parquet`（source 欄 = '
                                     'data.gov.tw:dataset:6100，2012-07～2026-09，171 列；\n'
                                     '        #   量測日 2026-10-23）實算：最高 2021-04 68.7、最低 2023-01 40.4；2020-04 '
                                     '47.6、2022-12 43.7\n'
                                     '        #   （後兩者與 `tab_edu` PMI 章節歷史表一致）。\n'
                                     "        'historical_anchor': '2021/4 高點 68.7｜2023/1 低點 40.4｜2020/4 疫情 "
                                     "47.6｜2022/12 43.7'\n"
                                     "                             '（官方序列 data.gov.tw 6100，2012/7 才創編；榮枯線 50 "
                                     "為定義值）',\n"
                                     "        'upstream': '全球終端需求、電子與半導體供應鏈訂單、原物料價格',\n"
                                     "        'downstream': '台灣出口與製造業營收 → 台股電子權值股獲利 → ^TWII',\n"
                                     '    },\n',
                                     '        ],\n'
                                     "        'pair_with': ['美國核心 CPI（CPILFESL）', '台灣出口 YoY', '費半 SOX'],\n"
                                     "        'historical_anchor': '2008 雷曼跌至 33.1｜2020 疫情 41.5｜2021 復甦高點 "
                                     "63.7',\n"
                                     "        'upstream': '訂單能見度、企業 CapEx、全球需求',\n"
                                     "        'downstream': '台灣出口（領先 1–2 季）→ 台股科技股獲利 → ^SOX & ^TWII',\n"
                                     '    },\n'),
                                    ('        # 技術備忘:v18.142 由 IMF IFS(VALEXPTWM052N)改採 OECD MEI,月延遲短 10 '
                                     '個月。\n'
                                     "        # 📌 DEC-075 批 1' 回修（QA1 S-4，2026-10-23，有意識的修改，⛔ 不是漏刪）：\n"
                                     "        #   ~~'本系統採用 OECD 的統計版本，比另一個常見的 IMF 版本早約 10 個月拿到最新月份資料。'~~\n"
                                     '        #   —— 與燈名「台灣出口金額 '
                                     'YoY（海關）」矛盾，且不符實際取數鏈：`macro_snapshot.fetch_export_block`\n'
                                     '        #   首源是主計總處統計資訊網（stat.gov.tw），其次 FRED API（OECD MEI '
                                     '系列）、海關進出口統計\n'
                                     '        #   （data.gov.tw／opendata.customs.gov.tw dataset 6053）、FRED '
                                     'CSV、財政部 CKAN；OECD 只是備援之一。\n'
                                     "        'meaning': '台灣每月出口金額年增率，全球景氣與台廠訂單能見度的核心指標'\n"
                                     "                   '（台灣 GDP 約 60% 來自出口）。'\n"
                                     "                   '本系統依序取主計總處統計資訊網、OECD（經 FRED）、海關進出口統計等來源，'\n"
                                     "                   '取第一個有值的那一源（畫面「命中來源」會標明本輪用的是哪一個）。',\n"
                                     "        'how_to_read': [\n",
                                     '        # 技術備忘:v18.142 由 IMF IFS(VALEXPTWM052N)改採 OECD MEI,月延遲短 10 '
                                     '個月。\n'
                                     "        'meaning': '台灣每月出口金額年增率，全球景氣與台廠訂單能見度的核心指標'\n"
                                     "                   '（台灣 GDP 約 60% 來自出口）。'\n"
                                     "                   '本系統採用 OECD 的統計版本，比另一個常見的 IMF 版本'\n"
                                     "                   '早約 10 個月拿到最新月份資料。',\n"
                                     "        'how_to_read': [\n")),
 'src/services/ai_qa_service.py': (('        "請如實說明這一點,**不得**用其他工具的數字或自己的判斷推估總分/等級/名次。"\n'
                                    '        # DEC-075 回修（MUST-2）：缺真實廣度 ⇒ ⛔ 不給「一鍵更新」救法（I-4）；其餘原因逐字照舊。\n'
                                    '        + ("更新資料不會改變這個狀態:要等正式的市場廣度(漲跌家數)資料來源接上,"\n'
                                    '           "**不得**建議使用者靠更新資料解決。"\n'
                                    '           if getattr(dec, "breadth_unevaluated", False) else\n'
                                    '           "救法:先開 🌍 總經頁按「🚀 一鍵更新全部數據」讓紅綠燈算出結論,再問一次。")\n'
                                    '        + "不受影響、仍可正常使用:財務體質(get_financial_health)、"\n'
                                    '        "停損與倉位(get_risk_plan)、大盤籌碼(get_market_leading)、ETF '
                                    '品質(get_etf_quality)。"\n',
                                    '        "請如實說明這一點,**不得**用其他工具的數字或自己的判斷推估總分/等級/名次。"\n'
                                    '        "救法:先開 🌍 總經頁按「🚀 一鍵更新全部數據」讓紅綠燈算出結論,再問一次。"\n'
                                    '        "不受影響、仍可正常使用:財務體質(get_financial_health)、"\n'
                                    '        "停損與倉位(get_risk_plan)、大盤籌碼(get_market_leading)、ETF '
                                    '品質(get_etf_quality)。"\n'),
                                   ('    _ms = _macro_state(require_valid_risk_cap=True) if '
                                    'require_valid_risk_cap else _macro_state()\n'
                                    '    from shared.regime_arbiter import is_breadth_unevaluated, '
                                    'unevaluated_breadth_explain\n'
                                    '    if is_breadth_unevaluated(_ms):\n'
                                    '        # 📌 QA-4 S-1（2026-10-23，有意識的修改，⛔ '
                                    '不是漏刪）：~~`UNEVALUATED_BREADTH_EXPLAIN`（「目前只有…代理值」）~~\n'
                                    '        #   在 ^TWII 全滅（連代理值也沒有）時不屬實 ⇒ 依本輪有沒有被擋下的代理值二選一；拿不準 ⇒ 中性句。\n'
                                    '        try:\n'
                                    '            from src.services.allocation_service import '
                                    'get_breadth_proxy_presence\n'
                                    '            _proxy = get_breadth_proxy_presence()\n'
                                    '        except Exception as _e:  # noqa: BLE001 — 拿不準 ⇒ 中性句（⛔ 不猜任何一邊）\n'
                                    '            print(f"[ai_qa] get_breadth_proxy_presence 失敗：{_e!r} —— '
                                    '改用中性句")\n'
                                    '            _proxy = None\n'
                                    '        # DEC-075 回修（MUST-2）：缺真實廣度 ⇒ ⛔ 不說「macro_state.json '
                                    '無快照」（檔案可能有效，只是 (a) 不採用）、\n'
                                    '        #   ⛔ 不叫人一鍵更新（I-4）。其餘未評估原因的既有文案逐字照舊（下一段）。\n'
                                    '        return {"ok": False,\n'
                                    '                "error": (unevaluated_breadth_explain(_proxy) + "。"\n'
                                    '                          "(§1:未評估就是未評估,**不退回「中性/震盪」當預設**;"\n'
                                    '                          "請勿把「未評估」講成「市場中性」,也**不得**建議使用者靠更新資料解決。)")}\n'
                                    '    if not isinstance(_ms, dict) or not _ms.get("is_loaded"):\n',
                                    '    _ms = _macro_state(require_valid_risk_cap=True) if '
                                    'require_valid_risk_cap else _macro_state()\n'
                                    '    if not isinstance(_ms, dict) or not _ms.get("is_loaded"):\n')),
 'src/services/allocation_service.py': (('\n'
                                         'def get_breadth_proxy_presence() -> bool | None:\n'
                                         '    """新 UI「缺真實市場廣度 ⇒ 未評估」文案二選一用的訊號（QA-4 S-1，2026-10-23；**純顯示**）。\n'
                                         '\n'
                                         '    讀 session 交給 L3 `section_inputs.breadth_proxy_presence`：True ＝ '
                                         '本輪有代理（估算）廣度值被擋下、\n'
                                         '    False ＝ 連代理值也沒有、None ＝ 拿不準（含讀不出來）⇒ 呼叫端用兩種情境都屬實的中性句。\n'
                                         '    ⛔ 判燈、計分、位階、建議持股一律不讀本函式。\n'
                                         '    """\n'
                                         '    try:\n'
                                         '        from src.services.section_inputs import '
                                         'breadth_proxy_presence\n'
                                         '        return breadth_proxy_presence(st.session_state)\n'
                                         '    except Exception as _e:  # noqa: BLE001 — 讀不出來 ⇒ 拿不準 ⇒ 中性句（⛔ '
                                         '不猜任何一邊）\n'
                                         "        print(f'[allocation] get_breadth_proxy_presence failed: "
                                         "{type(_e).__name__}: {_e} —— 改用中性句')\n"
                                         '        return None\n'
                                         '\n'
                                         '\n'
                                         'def get_allocation_sleeves() -> dict[str, int] | None:\n',
                                         '\ndef get_allocation_sleeves() -> dict[str, int] | None:\n'),),
 'src/services/dividend_station_service.py': (('\n'
                                               '    from shared.regime_arbiter import '
                                               'SOURCE_UNEVALUATED_BREADTH as '
                                               '_RA_SOURCE_UNEVALUATED_BREADTH\n'
                                               '    _regime = str(_state.get("regime", "unknown") or '
                                               '"unknown")\n',
                                               '\n'
                                               '    _regime = str(_state.get("regime", "unknown") or '
                                               '"unknown")\n'),
                                              ('        "posture_range": _posture_range,\n'
                                               '        # DEC-075 '
                                               '回修（MUST-2，schema-additive）：未評估原因是「缺真實市場廣度」（契約 source 旗標）。\n'
                                               '        "breadth_unevaluated": _state.get("source") == '
                                               '_RA_SOURCE_UNEVALUATED_BREADTH,\n'
                                               '    }\n',
                                               '        "posture_range": _posture_range,\n    }\n')),
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
 'src/services/macro_fetch_orchestrator.py': (("                    _df_i = _df_i[_df_i['date'] == _ld_i]\n"
                                               '                    # 2026-09-27(加性,⛔ 不改下兩行的 fillna(0))[📌 '
                                               "DEC-075 批 1' 起 fillna(0) 已拿掉,見下方 DH-FOREIGN-FILL0]:buy / "
                                               'sell 欄缺席或\n'
                                               '                    #   外資列不可解析時,下面會算出「假淨額」(缺 buy → '
                                               '淨額=−sell;兩欄都缺 → 0)。\n',
                                               "                    _df_i = _df_i[_df_i['date'] == _ld_i]\n"
                                               '                    # 2026-09-27(加性,⛔ 不改下兩行的 fillna(0)):buy '
                                               '/ sell 欄缺席或\n'
                                               '                    #   外資列不可解析時,下面會算出「假淨額」(缺 buy → '
                                               '淨額=−sell;兩欄都缺 → 0)。\n'),
                                              ('                        _fm_dealer_unobserved = '
                                               'bool(_fm_dealer_rows.any())\n'
                                               "                    # ── DH-FOREIGN-FILL0（DEC-075 批 1'，客戶 "
                                               '2026-10-23「外資缺值不得補 0」；行為變更，\n'
                                               '                    #    有意識的修改，⛔ '
                                               '不是漏刪）──────────────────────────────────────────────\n'
                                               "                    # ~~_df_i['buy'] = "
                                               "_pd.to_numeric(_df_i.get('buy', 0), "
                                               "errors='coerce').fillna(0)~~\n"
                                               "                    # ~~_df_i['sell'] = "
                                               "_pd.to_numeric(_df_i.get('sell', 0), "
                                               "errors='coerce').fillna(0)~~\n"
                                               '                    # 舊寫法把缺值補 0 再相減 ⇒ 缺 buy 時淨額＝−sell（可達 '
                                               '±數百億的假觀測）；上方旗標\n'
                                               '                    # 只讓讀旗標的消費點避開，沒讀旗標的消費點照樣拿到假數字（§1）。\n'
                                               '                    # 現行：buy／sell 缺欄或不可解析 ⇒ 該列淨額 NaN；某類別任一列 '
                                               'NaN ⇒ 該類別 net=None\n'
                                               '                    # （顯式缺值，旗標照舊 —— `unobserved_net` '
                                               '判斷式與上方完全相同）。觀測值逐位不變。\n'
                                               '                    # 整欄缺席（回應形狀不對）⇒ 補救放棄、inst 維持空（與修前同一個結果 '
                                               '—— 修前是\n'
                                               "                    #   `_df_i.get('buy', 0)` 回純量 0 → "
                                               '`.fillna` AttributeError 意外落入 except；\n'
                                               '                    #   現在明講原因，不靠意外）。\n'
                                               "                    if 'buy' not in _df_i.columns or 'sell' "
                                               'not in _df_i.columns:\n'
                                               "                        raise ValueError('FinMind 回應缺 "
                                               "buy／sell 欄 → 補救放棄（不推淨額）')\n"
                                               "                    _df_i['buy'] = "
                                               "_pd.to_numeric(_df_i['buy'], errors='coerce')\n"
                                               "                    _df_i['sell'] = "
                                               "_pd.to_numeric(_df_i['sell'], errors='coerce')\n"
                                               "                    _df_i['_net'] = ((_df_i['buy'] - "
                                               "_df_i['sell']) / TWD_PER_YI).round(2)  # 元 → 億(§4.1)；缺值 → "
                                               'NaN\n'
                                               '\n'
                                               '                    def _fm_add(_prev, _v):\n'
                                               '                        """類別加總：任一列缺值（NaN／None）⇒ 整類 None（⛔ '
                                               '不以 0 頂替、不跳過該列）。"""\n'
                                               '                        if _prev is None or _v is None or _v '
                                               '!= _v:\n'
                                               '                            return None\n'
                                               '                        return round(_prev + _v, 2)\n'
                                               '                    # FinMind name 欄為英文 key(Foreign_Investor '
                                               '/ Investment_Trust / Dealer_*)\n',
                                               '                        _fm_dealer_unobserved = '
                                               'bool(_fm_dealer_rows.any())\n'
                                               "                    _df_i['buy'] = "
                                               "_pd.to_numeric(_df_i.get('buy', 0), "
                                               "errors='coerce').fillna(0)\n"
                                               "                    _df_i['sell'] = "
                                               "_pd.to_numeric(_df_i.get('sell', 0), "
                                               "errors='coerce').fillna(0)\n"
                                               "                    _df_i['_net'] = ((_df_i['buy'] - "
                                               "_df_i['sell']) / TWD_PER_YI).round(2)  # 元 → 億(§4.1)\n"
                                               '                    # FinMind name 欄為英文 key(Foreign_Investor '
                                               '/ Investment_Trust / Dealer_*)\n'),
                                              ("                            inst.setdefault('_f', 0)\n"
                                               "                            inst['_f'] = _fm_add(inst['_f'], "
                                               '_net)\n'
                                               "                        elif _cat == '投信':\n"
                                               "                            inst['投信'] = {'net': (None if "
                                               '_net != _net else _net)}\n'
                                               "                        elif _cat == '自營':\n"
                                               "                            inst.setdefault('_d', 0)\n"
                                               "                            inst['_d'] = _fm_add(inst['_d'], "
                                               '_net)\n'
                                               "                    if '_f' in inst:\n",
                                               "                            inst.setdefault('_f', 0)\n"
                                               "                            inst['_f'] = round(inst['_f'] + "
                                               '_net, 2)\n'
                                               "                        elif _cat == '投信':\n"
                                               "                            inst['投信'] = {'net': _net}\n"
                                               "                        elif _cat == '自營':\n"
                                               "                            inst.setdefault('_d', 0)\n"
                                               "                            inst['_d'] = round(inst['_d'] + "
                                               '_net, 2)\n'
                                               "                    if '_f' in inst:\n"),
                                              ("                    if _fm_foreign_unobserved and '外資及陸資' in "
                                               'inst:\n'
                                               '                        # DH-FOREIGN-FILL0：~~淨額為 fillna(0) '
                                               '推出的假值~~ → 淨額為缺值（None）\n'
                                               "                        print('[FinMind-Inst] ⚠️ 外資列 "
                                               "buy/sell 缺值 → 外資淨額為缺值（None，'\n"
                                               "                              '不補 0）;foreign_net "
                                               "燈與讀旗標的消費點走缺值路徑')\n"
                                               '                    inst = InstNetDict(\n',
                                               "                    if _fm_foreign_unobserved and '外資及陸資' in "
                                               'inst:\n'
                                               "                        print('[FinMind-Inst] ⚠️ 外資列 "
                                               "buy/sell 缺值 → 淨額為 fillna(0) 推出的'\n"
                                               "                              '假值;foreign_net "
                                               "燈視為缺值(既有消費點照舊)')\n"
                                               '                    inst = InstNetDict(\n')),
 'src/services/macro_refresh_service.py': (('\n'
                                            'def warroom_written_detail(health_missing: bool, regime_source: '
                                            'Any) -> str:\n'
                                            '    """STEP_WARROOM 寫入成功時的步驟說明（純函式；QA2 S-1 回修抽出以便行為測試）。\n'
                                            '\n'
                                            '    DEC-074 B／DEC-075 '
                                            'D-1(a)（2026-10-23）：健康分未評估的**原因**是「缺真實市場廣度」時，\n'
                                            '    既有那句（「兩條腿都缺」「位階會改讀 macro_state.json」）兩半都不屬實 ⇒ 換成屬實的那句；\n'
                                            '    其餘情形逐字照舊。⛔ 不寫「重新抓取」之類的指引（重跑不會讓代理值變成可計分）。\n'
                                            '    📌 QA-4 S-1 連帶（2026-10-23，有意識的修改，⛔ 不是漏刪；決策者 AI 總管）：~~只在 '
                                            '`regime_source` 是 breadth 時才換~~ ——\n'
                                            '    DEC-075 D-1(a) 回修（QA3 MUST-R1）起，代理廣度不計分（L0 '
                                            '`BREADTH_PROXY_SCORING_ENABLED` 為 False）時\n'
                                            '    warroom 在而健康分缺 ⇒ `get_macro_state()` **不論 L2 '
                                            '標的原因**都判位階未評估、⛔ 不改讀 macro_state.json ⇒\n'
                                            '    ^TWII 全滅（L2 標 `unloaded`）時舊句「位階若有可用的 macro_state.json '
                                            '會改讀它」不屬實。選擇條件改與\n'
                                            '    `get_macro_state` 的 `_wr_breadth` 同口徑；旗標開時逐字照舊。\n'
                                            '    """\n'
                                            '    from shared import regime_arbiter as _RA_wr\n'
                                            '    from shared.signal_thresholds import '
                                            'BREADTH_PROXY_SCORING_ENABLED as _BPSE_wr\n'
                                            '    if health_missing and (regime_source == '
                                            '_RA_wr.SOURCE_UNEVALUATED_BREADTH or not _BPSE_wr):\n'
                                            '        return ("寫入 warroom_summary"\n'
                                            '                "（⚠️ 健康分因缺真實市場廣度（漲跌家數）未評估 —— 代理估算值依 DEC-074 '
                                            '不計分："\n'
                                            '                "建議持股的姿態帶與市場位階一併未評估（DEC-075，不改讀 '
                                            'macro_state.json）；"\n'
                                            '                "更新資料不會改變此狀態）")\n'
                                            '    return ("寫入 warroom_summary"\n'
                                            '            + ("（⚠️ 健康分兩條腿都缺 → `get_macro_state()` 把這份 warroom '
                                            '視同**未載入**："\n'
                                            '               "建議持股的姿態帶算不出來；市場位階若有可用的 macro_state.json 會改讀它）"\n'
                                            '               if health_missing else ""))\n'
                                            '\n'
                                            '\n'
                                            'def refresh_macro_now(*, mode: str = MODE_WARM,\n',
                                            '\ndef refresh_macro_now(*, mode: str = MODE_WARM,\n'),
                                           ('        if _wr_res.written:\n'
                                            '            # DEC-074 B／DEC-075 '
                                            'D-1(a)（2026-10-23）：健康分未評估的**原因**是「缺真實市場廣度」時，\n'
                                            '            #   下面那句既有說明（「兩條腿都缺」「位階會改讀 macro_state.json」）兩半都不屬實 '
                                            '⇒ 換成屬實的那句；\n'
                                            '            #   其餘情形逐字照舊。⛔ 不寫「重新抓取」之類的指引（重跑不會讓代理值變成可計分）。\n'
                                            '            _step(STEP_WARROOM, True,\n'
                                            '                  warroom_written_detail(\n'
                                            '                      _wr_res.health_missing,\n'
                                            '                      (st.session_state.get("warroom_summary") '
                                            'or {}).get("regime_source"))\n'
                                            '                  + _stale_inputs_note)\n',
                                            '        if _wr_res.written:\n'
                                            '            _step(STEP_WARROOM, True,\n'
                                            '                  "寫入 warroom_summary"\n'
                                            '                  + ("（⚠️ 健康分兩條腿都缺 → `get_macro_state()` 把這份 '
                                            'warroom 視同**未載入**："\n'
                                            '                     "建議持股的姿態帶算不出來；市場位階若有可用的 macro_state.json '
                                            '會改讀它）"\n'
                                            '                     if _wr_res.health_missing else "")\n'
                                            '                  + _stale_inputs_note)\n')),
 'src/services/macro_state_locker.py': (('\n'
                                         '    📌 DEC-075 D-1(a)（2026-10-23，含 QA3 MUST-R1 回修）：warroom '
                                         '**存在**而健康分非有限時，第 3 條**不生效** ——\n'
                                         '    原因標「缺真實廣度」（`SOURCE_UNEVALUATED_BREADTH`）、或代理廣度不計分\n'
                                         '    （`shared.signal_thresholds.BREADTH_PROXY_SCORING_ENABLED` 為 '
                                         "False）⇒ 位階 'unknown'、`is_loaded=False`。\n"
                                         '    旗標為 True 且原因不是廣度時照舊退第 3 條。warroom **不存在**時第 3 條照舊生效（本批未改）。\n'
                                         '\n'
                                         '    Returns:\n',
                                         '\n    Returns:\n'),
                                        ('    _wr_ok = bool(_wr) and '
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
                                         '    # ── DEC-075 D-1(a) 回修（QA3 MUST-R1，2026-10-23，行為變更，有意識的修改，⛔ '
                                         '不是漏刪）────────────\n'
                                         '    # 舊讀法（上段第 3 句）：「⚠️ 只限 breadth 原因：其他原因的 health 非有限 … 照舊視同 '
                                         'warroom 不存在、退檔案位階」。\n'
                                         '    # 破口：^TWII 全滅時（ADL 與旌旗備援兩個代理廣度都源自 ^TWII ⇒ '
                                         '旌旗整包缺、大盤分也缺、法人／期貨還在），\n'
                                         '    #   L2 `calc_traffic_light` 沒有「被擋下的代理值」可觸發 breadth 原因 ⇒ 標 '
                                         '`SOURCE_UNLOADED`\n'
                                         '    #   ⇒ 舊讀法退回 `macro_state.json` 規則引擎位階、`is_loaded=True` ⇒ AI '
                                         '評分用該位階權重、找標的頁套濾網\n'
                                         '    #   ＝ DEC-075 不採用的 (b)（「資料越少、結論越多」）。\n'
                                         '    # '
                                         '新讀法：代理廣度不計分（`shared.signal_thresholds.BREADTH_PROXY_SCORING_ENABLED` '
                                         '為 False）時，\n'
                                         '    #   repo 內沒有任何能讓健康分成立的真實廣度 ⇒ warroom 存在而 health 非有限，**不論 L2 '
                                         '標的原因為何**，\n'
                                         '    #   健康分都必然受「缺真實廣度」所限 ⇒ 位階一併未評估（與上方 breadth 原因分支**同一輸出**），⛔ '
                                         '不退檔。\n'
                                         '    #   L2 的原因標記／擋燈文案／油門／explainer 一律不動（QA3 實測放寬 L2 會讓失敗態 golden '
                                         '變紅）。\n'
                                         '    # 舊理由（「非 breadth 原因的未評估，檔案位階是合法的第 3 順位來源」）在旗標開啟（代理計分）時仍成立 ——\n'
                                         '    #   旗標開 ⇒ 本條不觸發、行為同上段舊讀法；被權衡掉的只是「旗標關時仍容許退檔」。\n'
                                         '    # warroom 不存在（`not _wr`）的路徑**本條不碰**（總管裁定事項，見回報）。\n'
                                         '    _wr_no_real_breadth = (bool(_wr) and not _wr_ok\n'
                                         '                           and not '
                                         '_ST.BREADTH_PROXY_SCORING_ENABLED)\n'
                                         '    _wr_breadth = (bool(_wr) and not _wr_ok\n'
                                         '                   and (_wr.get("regime_source") == '
                                         '_RA.SOURCE_UNEVALUATED_BREADTH\n'
                                         '                        or _wr_no_real_breadth))\n'
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
 'src/services/macro_v2_service.py': (('    "us_core_cpi": "CPILFESL",\n'
                                       "    # ISM 教學對映（DEC-075 批 1'，客戶 2026-10-23「修正 ISM 教學對映」；修正錯誤，有意識的更正，\n"
                                       '    #   ⛔ 不是漏刪）：~~"ism_pmi": "NAPM"~~ —— 這盞燈的值是**台灣製造業 '
                                       'PMI（CIER）**（session\n'
                                       '    #   `ism_pmi` 的實際來源，`VN1-MT-SSOT-ISM`），卻導到美國 ISM '
                                       '的教學（meaning／歷史數字皆為美國）。\n'
                                       "    #   改導台灣 PMI 條目（`EDU_GUIDE['TW_PMI']`，原 NAPM 條目改名並換掉 ISM 文案）；⛔ "
                                       '不換來源、\n'
                                       '    #   不改門檻（`how_to_read` 一行未動，同一組 PMI token）。\n'
                                       '    "ism_pmi": "TW_PMI",\n'
                                       '    "dxy": "DX-Y.NYB",\n',
                                       '    "us_core_cpi": "CPILFESL",\n'
                                       '    "ism_pmi": "NAPM",\n'
                                       '    "dxy": "DX-Y.NYB",\n'),),
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
                                      '    MA200_WINDOW_DAYS,  # 回修 QA2 S-2：常數下沉 L0（原定義在本檔）\n'
                                      ')\n'
                                      'from shared.macro_provenance import M1B_PROXY_VALUE_NOTE  # '
                                      'DL-f1-s23：代理註記（L0 SSOT，K1）\n',
                                      '# v18.449:市場廣度中性門檻 SSOT(原 inline `1.0`，尺度語意錯誤，見下方 market_regime '
                                      'docstring）\n'
                                      'from shared.signal_thresholds import M1B_M2_LEG_ENABLED, '
                                      'MARKET_BREADTH_NEUTRAL_PCT\n'
                                      'from shared.macro_provenance import M1B_PROXY_VALUE_NOTE  # '
                                      'DL-f1-s23：代理註記（L0 SSOT，K1）\n'),
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
                                       ('    if _jq_info:\n'
                                        '        # DEC-074 B（客戶 2026-10-23）：代理（估算）廣度不得計分 —— '
                                        '本列是健康分對帳（兩種演算法各算一次），\n'
                                        '        #   一樣是計分路徑 ⇒ 經 L0 `jingqi_for_scoring`：有值但為代理 ⇒ 缺值（⛔ 不退回 '
                                        'warroom）。\n'
                                        '        #   ⚠️ 只在「有值且代理」時才擋：沒有 avg 的既有缺值路徑（含「不退回 warroom」）一位未動。\n'
                                        '        _jq_proxy_drop = (_get(_jq_info, "avg") is not None) and '
                                        'not jingqi_for_scoring(_jq_info)\n'
                                        '        _jq = _get(_jq_info, "avg")      # 沒有 avg ⇒ None（缺值），⛔ 不退回 '
                                        'warroom（可能是舊頁籤殘留）\n'
                                        '        if _jq_proxy_drop:\n'
                                        '            _jq = None\n'
                                        '        # 📌 批 Z62（Z60 更正，上行註解保留）：Z60 起新 UI 也會寫 warroom，但其 '
                                        '`jingqi_avg` 是由\n',
                                        '    if _jq_info:\n'
                                        '        _jq = _get(_jq_info, "avg")      # 沒有 avg ⇒ None（缺值），⛔ 不退回 '
                                        'warroom（可能是舊頁籤殘留）\n'
                                        '        # 📌 批 Z62（Z60 更正，上行註解保留）：Z60 起新 UI 也會寫 warroom，但其 '
                                        '`jingqi_avg` 是由\n')),
 'src/services/section_inputs.py': (('    elif wr5:\n'
                                     '        # 📌 DEC-075 回修（QA1 S-6 連帶，2026-10-23）：`is_breadth_proxy` 改 '
                                     'fail-safe（缺旗標＝代理）。\n'
                                     '        #   warroom 的 `jingqi_avg` 是 `calc_traffic_light` 的**計分值** '
                                     '`jqavg` —— 代理時本來就是 None，\n'
                                     '        #   非 None 只可能是真值 ⇒ 合成時帶 `is_proxy=False`（None 時照舊無值，旗標不影響）。\n'
                                     "        _wr_jq = wr5.get('jingqi_avg')\n"
                                     "        jq = {'avg': _wr_jq, 'is_proxy': False} if _wr_jq is not None "
                                     "else {'avg': _wr_jq}\n"
                                     '    else:\n',
                                     '    elif wr5:\n'
                                     "        jq = {'avg': wr5.get('jingqi_avg')}\n"
                                     '    else:\n'),
                                    ('    )\n'
                                     '\n'
                                     '\n'
                                     'def breadth_proxy_presence(state: Optional[dict]) -> Optional[bool]:\n'
                                     '    """紅綠燈當輪的輸入裡有沒有「被擋下的代理（估算）廣度值」（QA-4 S-1，2026-10-23；純顯示用）。\n'
                                     '\n'
                                     "    取 `load_section_inputs(state)` 的 `jingqi_info` 與 `cl_data['adl']` "
                                     '—— **與 `calc_traffic_light`\n'
                                     '    吃的是同一份**（含 warroom 合成的旌旗退路）—— 交給 L0 '
                                     '`shared.macro_provenance.breadth_proxy_held_back`。\n'
                                     '    回 True（有代理值被擋下）／False（連代理值也沒有）／None（拿不準 ⇒ 呼叫端用中性句）。\n'
                                     '    ⛔ 判燈、計分、位階一律不讀本函式。\n'
                                     '    """\n'
                                     '    from shared.macro_provenance import breadth_proxy_held_back\n'
                                     '    if state is None:\n'
                                     '        return None\n'
                                     '    _inp = load_section_inputs(state)\n'
                                     '    _cd = _inp.cl_data if isinstance(_inp.cl_data, dict) else {}\n'
                                     "    return breadth_proxy_held_back(_inp.jingqi_info, _cd.get('adl'))\n",
                                     '    )\n')),
 'src/ui/pages/reconcile_panel.py': (('    if _jqavg is None:\n'
                                      '        # DEC-075 回修（QA1 S-1，2026-10-23，有意識的修改，⛔ 不是漏刪）：~~`_jingqi = '
                                      "_ss('jingqi_info', {}) or {}`~~\n"
                                      '        #   —— 健康分對帳是計分路徑：代理（估算）廣度依 DEC-074 不計分 ⇒ 經 L0 '
                                      '`jingqi_for_scoring`\n'
                                      '        #   （與 L3 `reconcile_service.health_inputs` 同口徑）。warroom '
                                      '`jingqi_avg` 是計分值、代理時本來就是 None。\n'
                                      '        from shared.macro_provenance import jingqi_for_scoring\n'
                                      "        _jingqi = jingqi_for_scoring(_ss('jingqi_info', {}) or {}) or "
                                      '{}\n'
                                      "        _jqavg = _jingqi.get('avg')\n",
                                      '    if _jqavg is None:\n'
                                      "        _jingqi = _ss('jingqi_info', {}) or {}\n"
                                      "        _jqavg = _jingqi.get('avg')\n"),),
 'src/ui/render/macro_v2_cards.py': (('    value_note: str = ""\n'
                                      '    # DEC-074 B 回修（QA1 S-2，2026-10-23）：True ＝ 這一列只有代理（估算）廣度值，依 '
                                      'DEC-074 **不計分** ——\n'
                                      '    # 畫面照樣顯示值，但「N／M 項有資料」的 N 不算它（`tab_macro_v2.bucket_summary` 的 '
                                      '`n_no_value`）。\n'
                                      '    # 預設 False → 既有呼叫端與畫面逐字不變。\n'
                                      '    proxy_not_scored: bool = False\n'
                                      '\n',
                                      '    value_note: str = ""\n\n'),),
 'src/ui/tabs/macro/handlers.py': (("            _gate_reason = '兩個獨立來源(三大法人 / 期貨籌碼)同時失效 — 只剩 ^TWII 自我印證'\n"
                                    "        elif tl.get('health_unavailable_reason') == 'breadth':\n"
                                    '            # DEC-075 回修（QA1 MUST-2／QA2 '
                                    'S-4，2026-10-23）：健康分是因**缺真實市場廣度**而未評估 ——\n'
                                    '            #   下一支「兩條腿都缺」不屬實（大盤分可能在），只改字。\n'
                                    "            _gate_reason = '缺真實市場廣度（漲跌家數），代理估算值依 DEC-074 不計分 — 算不出健康度'\n"
                                    '        else:\n',
                                    "            _gate_reason = '兩個獨立來源(三大法人 / 期貨籌碼)同時失效 — 只剩 ^TWII 自我印證'\n"
                                    '        else:\n'),
                                   ('        )\n'
                                    '        if _tl_state == UI_FAILED and '
                                    "tl.get('health_unavailable_reason') == 'breadth':\n"
                                    '            # DEC-075 回修：這不是「來源取得失敗」，是缺正式資料來源 ⇒ 灰色說明、⛔ 不提更新按鈕（I-4）。\n'
                                    "            _cta_color = '#8b949e'\n"
                                    "            _cta_text = ('⬜ 市場廣度缺的是正式資料來源，更新資料不會改變；'\n"
                                    "                         '正式廣度資料接上之前，燈號維持未評估（依 DEC-074／DEC-075 "
                                    "不以其餘分項或另一套規則補出結論）。')\n"
                                    '        elif _tl_state == UI_FAILED:\n'
                                    '            _cta_color = TRAFFIC_RED\n',
                                    '        )\n'
                                    '        if _tl_state == UI_FAILED:\n'
                                    '            _cta_color = TRAFFIC_RED\n'),
                                   ('            # 所以永遠不會「缺席」,只會靜默變成最強利空)。改為據實列出缺哪條腿。\n'
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
                                    '                    # 回修 QA2 S-4：「代理估算的廣度值不計分」只在本輪真的有代理值被擋下時才講（沒抓到 ≠ '
                                    '代理）。\n'
                                    "                    _proxy_seen = any('代理' in str(_m) for _m in "
                                    '_missing_now)\n'
                                    "                    _msg += (f'\u3000🩺 **綜合健康度未評估：缺 {_leg_txt}**'\n"
                                    "                             '（依 DEC-074 不以其餘分項改權重補出分數'\n"
                                    "                             + ('，代理估算的廣度值不計分' if _proxy_seen else '') "
                                    "+ '）。')\n"
                                    '                else:\n'
                                    "                    _msg += (f'\u3000🩺 **綜合健康度未含 "
                                    "{_leg_txt}**，本次僅由其餘分項'\n"
                                    "                             '推算（權重已重新歸一化，非補中性值/非補 0），'\n"
                                    "                             '請降低對該分數的信賴。')\n"
                                    '            if _breadth_reason:\n'
                                    '                # 回修 QA2 S-4（2026-10-23，有意識的修改，⛔ '
                                    '不是漏刪）：~~先叫人一鍵更新、再說更新不會改變~~（自相矛盾）。\n'
                                    '                #   breadth 原因時：只有**其餘**缺項才給更新指引；市場廣度那一項明講更新不會改變（I-4）。\n'
                                    '                _other_missing = [_m for _m in _missing_now\n'
                                    "                                  if '旌旗指數' not in str(_m) and 'ADL "
                                    "騰落指標' not in str(_m)]\n"
                                    '                if _other_missing:\n'
                                    "                    _msg += ('\u3000其餘缺項（' + '、'.join(_other_missing) + "
                                    "'）可按「🚀 一鍵更新全部數據」補上；')\n"
                                    "                _msg += '\u3000市場廣度缺的是正式資料來源，更新資料不會改變。'\n"
                                    '            else:\n'
                                    "                _msg += '\u3000建議按「🚀 一鍵更新全部數據」後再操作。'\n"
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
 'src/ui/tabs/tab_edu.py': ((')\n'
                             "# ~~from shared.fred_series import FRED_NAPM~~ —— DEC-075 批 1'（2026-10-23）：PMI "
                             "教學卡 key 改名 'TW_PMI' 後\n"
                             '#   本檔已無讀者（下方註解中的 `FRED_NAPM` 為歷史紀錄），依 pyflakes 拿掉（有意識的刪除，⛔ 不是漏刪）。\n'
                             "from shared.macro_buckets import (  # F1 v19.184：cl_data['intl'] key 鏡像（有 "
                             'drift 守衛）\n',
                             ')\n'
                             'from shared.fred_series import FRED_NAPM\n'
                             "from shared.macro_buckets import (  # F1 v19.184：cl_data['intl'] key 鏡像（有 "
                             'drift 守衛）\n'),
                            ("    'CPILFESL':         'us_core_cpi',\n"
                             "    # DEC-075 批 1'（2026-10-23，有意識的更正，⛔ 不是漏刪）：PMI 教學卡 key `FRED_NAPM`（'NAPM'，美國 "
                             'ISM\n'
                             "    #   序列代號）已改名 'TW_PMI'（`data_registry.EDU_GUIDE` 該處註解）—— 只換 key，對映的 spec "
                             '不變。\n'
                             "    'TW_PMI':           'ism_pmi',\n"
                             "    'XTEXVA01TWM664S':  'tw_export',\n",
                             "    'CPILFESL':         'us_core_cpi',\n"
                             "    FRED_NAPM:          'ism_pmi',\n"
                             "    'XTEXVA01TWM664S':  'tw_export',\n"),
                            ("                    'CPILFESL':       (_macro.get('us_core_cpi') or "
                             "{}).get('yoy'),\n"
                             "                    'TW_PMI':         ((_macro.get('ism_pmi') or "
                             "{}).get('value') or   # DEC-075 批 1'：原 key FRED_NAPM\n"
                             "                                       (_macro.get('ism_pmi') or "
                             "{}).get('current')),\n",
                             "                    'CPILFESL':       (_macro.get('us_core_cpi') or "
                             "{}).get('yoy'),\n"
                             "                    FRED_NAPM:        ((_macro.get('ism_pmi') or "
                             "{}).get('value') or\n"
                             "                                       (_macro.get('ism_pmi') or "
                             "{}).get('current')),\n")),
 'src/ui/tabs/tab_macro_v2.py': (('from shared.macro_provenance import is_m1b_m2_proxy  # '
                                  'DL-f1-s17：代理值不計分（L0 SSOT）\n'
                                  'from shared.macro_provenance import (  # DEC-074 B：代理廣度只顯示不計分（L0 SSOT）\n'
                                  '    BREADTH_LAMP_KEYS, BREADTH_PROXY_VALUE_NOTE,\n'
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
                                  '        # ⚠️ 側車契約：L2 只在代理時才寫 `is_proxy=True`（非代理時逐鍵不變）⇒ 這裡讀**側車**只認明確 '
                                  'True，\n'
                                  '        #   ⛔ 不套 L0 `is_breadth_proxy` 的 fail-safe（那是給 `jingqi_info` 原始 '
                                  'dict 用的；套在側車上會把真值列也打灰）。\n'
                                  '        _breadth_proxy = spec.key in BREADTH_LAMP_KEYS and '
                                  'rec.get("is_proxy") is True\n'
                                  '        if _breadth_proxy:\n'
                                  '            band = classify_danger(None, spec)\n'
                                  '\n',
                                  '            band = classify_danger(None, spec)\n\n'),
                                 ('            value_note=(m1b_m2_proxy_badge(rec)\n'
                                  '                        if spec.key == "m1b_m2_gap" and has_value\n'
                                  '                        else (BREADTH_PROXY_VALUE_NOTE if _breadth_proxy '
                                  'and has_value else "")),\n'
                                  '            proxy_not_scored=bool(_breadth_proxy and has_value),\n'
                                  '        ))\n',
                                  '            value_note=(m1b_m2_proxy_badge(rec)\n'
                                  '                        if spec.key == "m1b_m2_gap" and has_value else '
                                  '""),\n'
                                  '        ))\n'),
                                 ('            "n_bad": sum(1 for r in members if r.state != "live"),\n'
                                  '            # 回修 QA1 S-2（DEC-074 B）：代理廣度列（只顯示、不計分）＝沒有可下判斷的值 ⇒ 一併算進 '
                                  'n_no_value。\n'
                                  '            "n_no_value": sum(1 for r in members\n'
                                  '                              if r.state in NO_VALUE_ROW_STATES or '
                                  'getattr(r, "proxy_not_scored", False)),\n'
                                  '        })\n',
                                  '            "n_bad": sum(1 for r in members if r.state != "live"),\n'
                                  '            "n_no_value": sum(1 for r in members if r.state in '
                                  'NO_VALUE_ROW_STATES),\n'
                                  '        })\n')),
 'src/ui/views/page_hold.py': (('    建議持股水位  L3 `services.allocation_service.get_allocation`\n'
                                '    廣度文案訊號  L3 `services.allocation_service.get_breadth_proxy_presence`  ← '
                                'QA-4 S-1（只讀 session、零 I/O；只選 ④⑤ 廣度未評估的說明句）\n'
                                '    N/M 盞可信度  L4 `ui.render.station_cards.aggregate_judged` / '
                                '`tally_states` /\n',
                                '    建議持股水位  L3 `services.allocation_service.get_allocation`\n'
                                '    N/M 盞可信度  L4 `ui.render.station_cards.aggregate_judged` / '
                                '`tally_states` /\n'),
                               ('    error: str = ""\n'
                                '    #: DEC-075 回修（MUST-2）：未評估原因是「缺真實市場廣度」（L3 `get_station_macro` 原樣透傳）。\n'
                                '    breadth_unevaluated: bool = False\n'
                                '    #: QA-4 S-1（2026-10-23）：`breadth_unevaluated` 時，本輪有沒有被擋下的代理廣度值\n'
                                '    #: （L3 '
                                '`allocation_service.get_breadth_proxy_presence()`；True／False／None ＝ '
                                '拿不準）。只選文案，判態不讀。\n'
                                '    breadth_proxy: bool | None = None\n'
                                '\n'
                                '\n'
                                'def _breadth_proxy_presence() -> bool | None:\n'
                                '    """QA-4 S-1：L3 `get_breadth_proxy_presence()`；讀不出來 ⇒ None（中性句）。⛔ '
                                '判態不讀。"""\n'
                                '    try:\n'
                                '        from src.services.allocation_service import '
                                'get_breadth_proxy_presence\n'
                                '        return get_breadth_proxy_presence()\n'
                                '    except Exception as _e:  # noqa: BLE001 — 拿不準就用中性句，log 出聲（⛔ 不猜任何一邊）\n'
                                '        print(f"[views/page_hold] get_breadth_proxy_presence 失敗：{_e!r} —— '
                                '改用中性句")\n'
                                '        return None\n'
                                '\n',
                                '    error: str = ""\n\n'),
                               ('        posture_label=_clean_signal(_m.get("posture_label")),\n'
                                '        posture_range=str(_m.get("posture_range") or ""),\n'
                                '        breadth_unevaluated=bool(_m.get("breadth_unevaluated")),\n'
                                '        breadth_proxy=(_breadth_proxy_presence() if '
                                '_m.get("breadth_unevaluated") else None))\n'
                                '\n',
                                '        posture_label=_clean_signal(_m.get("posture_label")),\n'
                                '        posture_range=str(_m.get("posture_range") or ""))\n'
                                '\n'),
                               ('    risk_cap_disclosure: Any = None\n'
                                '    #: DEC-075 回修（MUST-2）：L3 `AllocationDecision.unevaluated_reason == '
                                "'breadth'`（缺真實市場廣度）。\n"
                                '    breadth_unevaluated: bool = False\n'
                                '    #: QA-4 S-1（2026-10-23）：同 `MacroReadout.breadth_proxy`（只選文案，判態不讀）。\n'
                                '    breadth_proxy: bool | None = None\n'
                                '\n',
                                '    risk_cap_disclosure: Any = None\n\n'),
                               ('        has_risk_cap=has_system_risk_cap(getattr(_a, "caps", ())),\n'
                                '        risk_cap_disclosure=getattr(_a, "risk_cap_disclosure", None),\n'
                                '        breadth_unevaluated=(getattr(_a, "unevaluated_reason", "") == '
                                '"breadth"),\n'
                                '        breadth_proxy=(_breadth_proxy_presence()\n'
                                '                       if getattr(_a, "unevaluated_reason", "") == '
                                '"breadth" else None))\n'
                                '\n',
                                '        has_risk_cap=has_system_risk_cap(getattr(_a, "caps", ())),\n'
                                '        risk_cap_disclosure=getattr(_a, "risk_cap_disclosure", None))\n'
                                '\n'),
                               ('\n'
                                '#: DEC-075 回修（QA1 MUST-2，2026-10-23）：④ 總經位階／⑤ 建議持股水位在「缺真實市場廣度 ⇒ 未評估」時的 '
                                'why／where。\n'
                                '#: ⛔ 不叫人「到今天頁更新總經」（I-4：重跑不會讓代理值變成可計分）。其餘未評估原因的既有文案逐字不變。\n'
                                '#: 📌 QA-4 S-1（2026-10-23，有意識的修改，⛔ 不是漏刪；決策者 AI 總管）：DEC-075 D-1(a) 回修起這兩格也用在\n'
                                '#:   ^TWII 全滅（這一輪確實沒抓到、連代理值也沒有）那一態 ⇒ ~~why 開頭「已經去讀過，不是還沒讀」~~、\n'
                                '#:   ~~where 的「不是這一輪沒抓到」~~、以及 L0 說明句的「目前只有由加權指數推估的代理值」在那一態不屬實。\n'
                                '#:   現行：why 開頭只講本頁單點可驗的事（讀到的契約回報了這個原因）；說明句依 `breadth_proxy` 二選一\n'
                                '#:   （L0 `regime_arbiter.unevaluated_breadth_explain`；None ⇒ 中性句）；where '
                                '改為兩態都屬實的一句。\n'
                                'def _breadth_empty_why(breadth_proxy: bool | None = None) -> str:\n'
                                '    from shared.regime_arbiter import unevaluated_breadth_explain\n'
                                '    return ("**這不是本頁讀取失敗**：本頁讀到的總經契約明確回報「因缺真實市場廣度而未評估」—— "\n'
                                '            + unevaluated_breadth_explain(breadth_proxy)\n'
                                '            + "；本站**不以「中性」代替未評估**，也不填一個看起來合理的區間")\n'
                                '\n'
                                '\n'
                                '_BREADTH_EMPTY_WHY: str = _breadth_empty_why()\n'
                                '_BREADTH_EMPTY_WHERE: str = (\n'
                                '    f"{NO_EXIT_MARKER} —— **這一格更新資料不會改變**：缺的是正式的市場廣度（漲跌家數）資料來源；"\n'
                                '    "正式廣度資料接上之前，這一格會一直是未評估")\n'
                                '\n'
                                '\n'
                                'def build_macro_stage_card(macro: MacroReadout) -> _Built:\n',
                                '\ndef build_macro_stage_card(macro: MacroReadout) -> _Built:\n'),
                               ('                            f"{ia_nav.where_to_find(ia_nav.PAGE_TODAY)}"))\n'
                                '    elif macro.breadth_unevaluated:   # UI_EMPTY，原因＝缺真實廣度（DEC-075 回修 '
                                'MUST-2；⛔ 不叫人重抓）\n'
                                '        _note = Note(now=MACRO_EMPTY_NOW, '
                                'why=_breadth_empty_why(macro.breadth_proxy),\n'
                                '                     where=_BREADTH_EMPTY_WHERE)\n'
                                '    else:   # UI_EMPTY\n',
                                '                            f"{ia_nav.where_to_find(ia_nav.PAGE_TODAY)}"))\n'
                                '    else:   # UI_EMPTY\n'),
                               ('                     where=(f"{NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者"))\n'
                                '    elif alloc.breadth_unevaluated:   # UI_EMPTY，原因＝缺真實廣度（DEC-075 回修 '
                                'MUST-2；⛔ 不叫人重抓）\n'
                                '        _note = Note(now=CAP_EMPTY_NOW, '
                                'why=_breadth_empty_why(alloc.breadth_proxy),\n'
                                '                     where=_BREADTH_EMPTY_WHERE)\n'
                                '    else:   # UI_EMPTY\n',
                                '                     where=(f"{NO_EXIT_MARKER} —— 請把上面那行訊息回報給維護者"))\n'
                                '    else:   # UI_EMPTY\n')),
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
                                 '#: 📌 QA-4 S-1（2026-10-23，有意識的修改，⛔ 不是漏刪；決策者 AI '
                                 '總管）：~~「不是這一輪沒抓到；目前只有由加權指數推估的\n'
                                 '#:   代理值」~~ —— DEC-075 D-1(a) 回修起本出口也用在 ^TWII 全滅（這一輪確實沒抓到、連代理值也沒有）那一態，\n'
                                 '#:   兩句在那一態不屬實。出口講的是「該怎麼辦」（兩態相同：等正式廣度來源），故改為兩態都屬實的一句；\n'
                                 '#:   「這一輪有沒有代理值」那件事實改由 '
                                 'why（`breadth_unevaluated_why()`）依資料二選一。物件身分照舊（`V2_EXIT_PHRASES`）。\n'
                                 'EXIT_WAIT_BREADTH_SOURCE: str = (\n'
                                 '    f"{NO_EXIT_MARKER} —— **這一格更新資料不會改變**：缺的是正式的市場廣度（漲跌家數）資料來源；"\n'
                                 '    "由加權指數推估的代理值依客戶裁示（DEC-074）只顯示、不計分，抓得到也不會讓這一格成立。"\n'
                                 '    "正式廣度資料接上之前，這一格會一直是未評估")\n'
                                 '\n'
                                 '_BREADTH_UNEVALUATED_WHY_TAIL: str = (\n'
                                 '    "依 DEC-074 不計分 ⇒ 健康分未評估；依 DEC-075 市場位階也一併未評估，"\n'
                                 '    "**不改用另一套規則引擎補出位階**，本站也不以缺值推導一個安全水位")\n'
                                 '\n'
                                 '#: 「缺真實市場廣度 ⇒ 未評估」的 why（卡① / 卡③ / 狀態列「總經」／三欄摘要「位階」共用一句）。\n'
                                 '#: 📌 QA-4 S-1（2026-10-23，有意識的修改，⛔ 不是漏刪）：~~「目前只有加權指數推估的代理值」~~ 在 ^TWII '
                                 '全滅時不屬實 ⇒\n'
                                 '#:   本常數改為兩態都屬實的**中性句**（拿不到區分訊號時用）；有訊號時走 `breadth_unevaluated_why()` 二選一。\n'
                                 'BREADTH_UNEVALUATED_WHY: str = (\n'
                                 '    "總經健康分需要真實市場廣度（漲跌家數），本站目前沒有正式的廣度資料來源；"\n'
                                 '    "由加權指數推估的代理值即使取得，也" + _BREADTH_UNEVALUATED_WHY_TAIL)\n'
                                 '#: 本輪**有**代理值、被擋下不計分（L3 `allocation_service.get_breadth_proxy_presence()` '
                                 '為 True）。\n'
                                 'BREADTH_UNEVALUATED_WHY_PROXY_HELD: str = (\n'
                                 '    "總經健康分需要真實市場廣度（漲跌家數），目前只有加權指數推估的代理值，" + '
                                 '_BREADTH_UNEVALUATED_WHY_TAIL)\n'
                                 '#: 本輪**連代理值也沒有**（`get_breadth_proxy_presence()` 為 False；例：^TWII 全滅）。\n'
                                 'BREADTH_UNEVALUATED_WHY_NO_PROXY: str = (\n'
                                 '    "總經健康分需要真實市場廣度（漲跌家數），這一輪紅綠燈的輸入裡也沒有任何廣度資料"\n'
                                 '    "（連加權指數推估的代理值也沒有）；即使取得代理值，也" + _BREADTH_UNEVALUATED_WHY_TAIL)\n'
                                 '\n'
                                 '\n'
                                 'def breadth_unevaluated_why(breadth_proxy: bool | None = None) -> str:\n'
                                 '    """缺真實廣度 ⇒ 未評估的 why：True（有代理值被擋下）／False（連代理值也沒有）／None（拿不準 ⇒ 中性句）。"""\n'
                                 '    if breadth_proxy is True:\n'
                                 '        return BREADTH_UNEVALUATED_WHY_PROXY_HELD\n'
                                 '    if breadth_proxy is False:\n'
                                 '        return BREADTH_UNEVALUATED_WHY_NO_PROXY\n'
                                 '    return BREADTH_UNEVALUATED_WHY\n'
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
                                 '= None,\n'
                                 '                             breadth_proxy: bool | None = None) -> Card:\n'
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
                                 '    `breadth_proxy=`（QA-4 S-1，選填，預設 None ⇒ '
                                 '中性句）：`get_breadth_proxy_presence()` 的回傳，只選 why 的那一句。\n'
                                 '    """\n',
                                 '    `now` 不動；`tab_today.py` 照舊一個字都不動。\n    """\n'),
                                ('    _note = card.note\n'
                                 '    if _note.where is CONTRACT_NO_EXIT_WHERE and '
                                 'regime_breadth_unevaluated(regime):\n'
                                 '        _note = dc_replace(_note, where=EXIT_WAIT_BREADTH_SOURCE, '
                                 'why=breadth_unevaluated_why(breadth_proxy))\n'
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
                                ('\n'
                                 'def _alloc_unloaded_why(regime: Mapping[str, Any] | None,\n'
                                 '                        breadth_proxy: bool | None = None) -> str:\n'
                                 '    """卡①「L3 建議持股契約回報未評估」的 why —— 依**實際缺的來源**組句（批 Z65 QA）。\n',
                                 '\n'
                                 'def _alloc_unloaded_why(regime: Mapping[str, Any] | None) -> str:\n'
                                 '    """卡①「L3 建議持股契約回報未評估」的 why —— 依**實際缺的來源**組句（批 Z65 QA）。\n'),
                                ('        return _head + "建議持股需要總經健康分算出姿態帶，本輪沒有取得" + _tail\n'
                                 '    if regime_breadth_unevaluated(regime):\n'
                                 '        # DEC-074 B：原因是缺真實市場廣度（代理不計分），⛔ 不寫成「本輪沒有值」（那暗示重抓會有）。\n'
                                 '        return _head + breadth_unevaluated_why(breadth_proxy)\n'
                                 '    _parts: list[str] = []\n',
                                 '        return _head + "建議持股需要總經健康分算出姿態帶，本輪沒有取得" + _tail\n'
                                 '    _parts: list[str] = []\n'),
                                ('                        l4_error: str = "",\n'
                                 '                        macro_attempt: tuple[str, str] | None = None,\n'
                                 '                        breadth_proxy: bool | None = None) -> tuple[Tile, '
                                 '...]:\n'
                                 '    """葉1 ① 今日結論 —— **三張並排的卡，沒有第四張「合成結論」**。\n',
                                 '                        l4_error: str = "",\n'
                                 '                        macro_attempt: tuple[str, str] | None = None) -> '
                                 'tuple[Tile, ...]:\n'
                                 '    """葉1 ① 今日結論 —— **三張並排的卡，沒有第四張「合成結論」**。\n'),
                                ('            紅綠燈步驟）。只影響「契約仍未評估」時卡① / 卡③ 的判態與文案；預設 None ⇒ 與修前逐一相同。\n'
                                 '        breadth_proxy: QA-4 S-1（2026-10-23）L3 '
                                 '`get_breadth_proxy_presence()` 的回傳。只在契約「缺真實廣度\n'
                                 '            ⇒ 未評估」時選卡① / 卡③ why 的那一句（True 有代理值被擋下／False 連代理值也沒有／None '
                                 '中性句）；\n'
                                 '            判態、出口一律不讀。\n'
                                 '\n',
                                 '            紅綠燈步驟）。只影響「契約仍未評估」時卡① / 卡③ 的判態與文案；預設 None ⇒ 與修前逐一相同。\n\n'),
                                ('            #    不是漏刪）：全稱句。規則引擎快照有值、只是健康分缺時，這句不屬實 ⇒ 依實際缺的來源組句。\n'
                                 '            _why = _alloc_unloaded_why(regime, breadth_proxy)\n'
                                 '            if _att_applies:\n',
                                 '            #    不是漏刪）：全稱句。規則引擎快照有值、只是健康分缺時，這句不屬實 ⇒ 依實際缺的來源組句。\n'
                                 '            _why = _alloc_unloaded_why(regime)\n'
                                 '            if _att_applies:\n'),
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
                                 '                     breadth_unevaluated_why(breadth_proxy) if '
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
                                ('\n'
                                 'def _load_breadth_proxy() -> bool | None:\n'
                                 '    """QA-4 S-1：L3 `get_breadth_proxy_presence()`（本輪有沒有被擋下的代理廣度值）。讀不出來 ⇒ '
                                 'None（中性句）。"""\n'
                                 '    try:\n'
                                 '        from src.services.allocation_service import '
                                 'get_breadth_proxy_presence\n'
                                 '        return get_breadth_proxy_presence()\n'
                                 '    except Exception as _e:  # noqa: BLE001 — 拿不準就用中性句，log 出聲（⛔ 不猜任何一邊）\n'
                                 '        print(f"[views/page_today] get_breadth_proxy_presence 失敗：{_e!r} —— '
                                 '改用中性句")\n'
                                 '        return None\n'
                                 '\n'
                                 '\n'
                                 'def _load_danger(readout: MacroReadout\n',
                                 '\ndef _load_danger(readout: MacroReadout\n'),
                                ('    (EXIT_FIX_CODE,               "需修程式"),\n'
                                 '    (EXIT_WAIT_BREADTH_SOURCE,    "等正式廣度資料來源"),   # DEC-074 B\n'
                                 '    (EXIT_ALERTS_PARTIAL,         "只更新得到一半"),\n',
                                 '    (EXIT_FIX_CODE,               "需修程式"),\n'
                                 '    (EXIT_ALERTS_PARTIAL,         "只更新得到一半"),\n'),
                                ('                        band_zh_color: Mapping[str, tuple[str, str]] | '
                                 'None = None,\n'
                                 '                        l4_error: str = "",\n'
                                 '                        regime: Mapping[str, Any] | None = None,\n'
                                 '                        breadth_proxy: bool | None = None) -> tuple[Tile, '
                                 '...]:\n'
                                 '    """葉1 ③ 三欄摘要 → `Tile`。**只換「風險」那一格，其餘照 `_tiles_of_cards()`。**\n',
                                 '                        band_zh_color: Mapping[str, tuple[str, str]] | '
                                 'None = None,\n'
                                 '                        l4_error: str = "") -> tuple[Tile, ...]:\n'
                                 '    """葉1 ③ 三欄摘要 → `Tile`。**只換「風險」那一格，其餘照 `_tiles_of_cards()`。**\n'),
                                ('                      band_zh_color=band_zh_color, l4_error=l4_error)\n'
                                 '         if _c.key == SUMMARY_RISK_KEY else '
                                 'Tile(contract_exit_retargeted(_c, regime, breadth_proxy)))\n'
                                 '        for _c in cards)\n',
                                 '                      band_zh_color=band_zh_color, l4_error=l4_error)\n'
                                 '         if _c.key == SUMMARY_RISK_KEY else '
                                 'Tile(contract_exit_retargeted(_c)))\n'
                                 '        for _c in cards)\n'),
                                ('    _regime, _regime_err = _load_regime()\n'
                                 '    # QA-4 S-1：「缺真實廣度 ⇒ 未評估」文案二選一的訊號（純顯示；判態／出口不讀）。\n'
                                 '    _breadth_proxy = _load_breadth_proxy()\n'
                                 '    # ⚠️【1】兩顆燈**各自一支 loader**：危險度不吃 regime、位階不吃 16 盞燈。\n',
                                 '    _regime, _regime_err = _load_regime()\n'
                                 '    # ⚠️【1】兩顆燈**各自一支 loader**：危險度不吃 regime、位階不吃 16 盞燈。\n'),
                                ('        _tiles_of_cards(status_bar_cards_with_sheet(\n'
                                 '            tuple(contract_exit_retargeted(_c, _regime, _breadth_proxy) '
                                 'for _c in _bar_cards),\n'
                                 '            build_sheet_binding_card(_sheet_state, error=_sheet_err))),\n',
                                 '        _tiles_of_cards(status_bar_cards_with_sheet(\n'
                                 '            tuple(contract_exit_retargeted(_c) for _c in _bar_cards),\n'
                                 '            build_sheet_binding_card(_sheet_state, error=_sheet_err))),\n'),
                                ('            band_zh_color=_band_zh, l4_error=_l4_err,\n'
                                 '            macro_attempt=_attempt, breadth_proxy=_breadth_proxy))\n'
                                 '\n',
                                 '            band_zh_color=_band_zh, l4_error=_l4_err,\n'
                                 '            macro_attempt=_attempt))\n'
                                 '\n'),
                                ('            danger_requested=_readout.requested, '
                                 'danger_source=_danger_src,\n'
                                 '            band_zh_color=_band_zh, l4_error=_l4_err, regime=_regime,\n'
                                 '            breadth_proxy=_breadth_proxy))\n'
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


def dec074_restore_edu_text(mp) -> None:
    """舊批次「舊 UI 教學頁整頁 golden」比對用：把 DEC-075 回修改過的兩欄教學文字暫時換回修前原文（monkeypatch）。

    改的是 `EDU_GUIDE['CPILFESL']['pair_with']`（NIT-4）與 `EDU_GUIDE['XTEXVA01TWM664S']['meaning']`（QA1 S-4）——
    兩欄的現行內容由 `tests/test_batch_z27.py::test_changed_cards_pinned` 整欄釘住；這裡只為了讓守「別的事」的
    舊 golden（三大法人、VIX 門檻用字…）照舊逐字比對，⛔ 不是洗掉本批的改動。
    """
    from src.data.core import data_registry as DR
    from tests.test_batch_z27 import _CPI_PAIR_PRE_DEC075, _EXPORT_MEANING_PRE_DEC075
    mp.setitem(DR.EDU_GUIDE, "CPILFESL", dict(DR.EDU_GUIDE["CPILFESL"], pair_with=list(_CPI_PAIR_PRE_DEC075)))
    mp.setitem(DR.EDU_GUIDE, "XTEXVA01TWM664S",
               dict(DR.EDU_GUIDE["XTEXVA01TWM664S"], meaning=_EXPORT_MEANING_PRE_DEC075))


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
