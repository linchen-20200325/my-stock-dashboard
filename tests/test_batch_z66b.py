"""批 Z66b —— 系統風險上限 Q1：Required Core 閘門 ＋ 新 UI 只認有效快照（客戶 2026-10-16 裁示）。

客戶裁示（逐意轉錄）：Required Core ＝ {VIX、台灣 PMI 當月、台灣 PMI 前月、外資期貨淨空單＋指數跌破 MA5}。
任一 Required Core 無法評估：⛔ 不產生新的系統風險上限；可沿用 7 天內最近一次**有效**快照；超過 7 天 →
「無法判定」；⛔ 不得因缺資料放寬風控。M1B／M2、PCR、BIAS240 為 Optional，缺時須揭露未評估項。
此為現有證據下的正式版本。

守：
1. L0 `shared.risk_cap_policy`：Required Core／Optional 與 L2／L3 鍵名一致、與紅線表一致、L0 零 L1+ import。
2. 寫端 `compute_and_lock_risk_cap`：每個核心項單獨缺 ⇒ 不寫、既有檔 bytes 不變、原因點名；VIX-only ⇒ 不寫；
   核心齊、Optional 缺 ⇒ 寫、`not_evaluated` 列出、蓋 `required_core_ok: True`＋規則版本。
3. 讀端 `get_macro_state(require_valid_risk_cap=True)`（新 UI／服務經 `get_allocation`／`get_macro_regime`／
   `run_agent` 傳入）：舊 UI 樣式檔、舊版本檔 ⇒ 無上限；6.9 天有效檔 ⇒ 有上限；7.1 天 ⇒ 無上限。
   預設（舊 UI 呼叫方式）一字不變。
4. 步驟報告：核心缺 ⇒ 點名核心項、不產生新上限、沿用 7 天內有效快照否則無法判定；Optional 未評估照揭露。
5. 突變：拿掉寫端閘門 ⇒ 紅；拿掉讀端戳記檢查 ⇒ 紅。
6. 還原鏈：本批（Z66 第二個 commit）的改動換回第一個 commit 的寫法。
L1 一律 mock；不連網。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原鏈（同 Z62／Z65／Z66 慣例）：把本批改動換回 Z66 第一個 commit（Q2）的寫法
#    ⚠️ 本段必須在任何 `from tests...` import 之前（舊批次測試檔會回頭 import 這裡）
# ══════════════════════════════════════════════════════════════════════════
# ── 還原組（自動產生：逐段 (現行, 修前)；⛔ 手改會讓 sha 對不上）──
#: Z66 第一個 commit（Q2）的原檔 sha256（`git show <該 commit>:<rel> | sha256sum`；寫死以免測試依賴 git）。
Z66B_BASE_SHA = {
    'shared/risk_cap_policy.py': 'bfea6fbb60656f73d41ca8f51be4aa8f87fc142e520618189264fa7892f63894',
    'src/services/ai_qa_service.py': 'e647a81b3e61bcb016b824f816725f16bcaf772baeacccdad963bce2c325fd31',
    'src/services/allocation_service.py': '0104faaa54f9206f9e34e8d719c7d624a3bab00ec7c040092435346afb43cc9a',
    'src/services/macro_engine_inputs.py': '714c2019e1bda5d4291a8151552303f6cffcc67ca64d845b3e274f47335a07cf',
    'src/services/macro_refresh_service.py': '776e738dd1f6e232b246281e8515d2a0b297cf0f6e3a475b48028a0412807f53',
    'src/services/macro_state_locker.py': '81d15e8e989220ac33a418dc88168b0a1c642a96770ffac3cd6204fc9687e94b',
    'src/services/risk_cap_apply.py': '15fcc94a2da095490840e39d1279fc319e966d5788f5ecbab670edfca7f2d3f8',
    'src/ui/views/page_hold.py': '232fb0cc6b403a0b0b26e00fab68aed6262318cbf4610e604c51d818653db4b1',
    'src/ui/views/page_today.py': 'e40227c7f1442da1c54b87bab66d1fafb1765d2746694db3383624132f099f8d',
    'src/ui/views/page_why.py': 'b44dd2cc232494b071641e19e60570eb9e04f7a49dc5ef3ed76603cd50ca94c5',
}
#: 這兩檔另有 `tests/test_batch_z56.py` 的還原鏈管（見 `z66b_revert_for` 的 `only`／`skip`）。
Z66B_VIA_Z56 = frozenset({"src/services/ai_qa_service.py", "src/ui/views/page_why.py"})
Z66B_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    'shared/risk_cap_policy.py': (
        ('客戶 2026-10-16 Q1：Required Core（下方 `REQUIRED_CORE_INPUTS`）任一無法評估 ⇒ **不產生新的系統風險上限**；\n可沿用 7 天內（`shared.staleness.MACRO_VERDICT_MAX_AGE_DAYS`）最近一次**有效**快照，超過 7 天 →「無法判定」；\n⛔ 不得因缺資料放寬風控。M1B／M2、PCR、BIAS240 為 Optional，缺時須揭露未評估項。\n⇒ 寫端（`risk_cap_apply`）核心齊全才寫、並蓋 `required_core_ok: True`；新 UI 讀端只認\n`is_valid_risk_cap_snapshot(...)` 為 True 的檔（舊 UI 寫的檔、v2 以前的檔一律不認 ⇒ 無上限 ⇒「無法判定」）。\n\n',
         ''),
        ('\nfrom types import MappingProxyType\nfrom typing import Any, Mapping\n',
         ''),
        ('                            不計分、不貼「資金緊縮」、不算「未評估」，回報為 `disabled_inputs`；\n                            ＋ 客戶 Q1：Required Core 全部可評估才寫檔，並蓋 `required_core_ok: True`\n                            （同一批 Z66 的第二個 commit；兩者都是 v2 的一部分，讀端兩欄都要）。\n',
         '                            不計分、不貼「資金緊縮」、不算「未評估」，回報為 `disabled_inputs`。\n'),
        ('\n\n# ── Required Core（客戶 2026-10-16 Q1；現有證據下的正式版本）────────────────────\nREQUIRED_CORE_INPUTS: tuple[str, ...] = (\n    "VIX_Index",             # VIX\n    "ISM_PMI_or_OECD_CLI",   # 台灣 PMI 當月（鍵名沿用引擎歷史命名；值是 CIER 台灣 PMI）\n    "PMI_Prev_Month",        # 台灣 PMI 前月（PMI 歷史 parquet 的真正前一資料月）\n    "Futures_Net_Short",     # 外資期貨淨空單（TX 當量口）\n    "Index_Below_MA5",       # 加權指數是否跌破 MA5（與外資期貨同屬硬否決紅線三）\n)\n"""系統風險上限的**必要核心輸入**（引擎鍵名；順序即報告順序）。任一無法評估 ⇒ 本輪不產生新上限。\n\n「無法評估」的判定與 L3 `macro_engine_inputs` 的硬紅線同一條（新鮮度非 FRESH 或計分值為 None）。\n「外資期貨淨空 ＋ 指數跌破 MA5」就是硬否決紅線三的那一對（`RED_LINE_INPUTS["futures_ma5"]`）——\n⚠️ 沒有「外資期貨部位的 MA5」這種東西，MA5 指的是加權指數。\n⛔ 鍵名在 L0 以字面寫（L0 不得 import L2 `dated_inputs`）；與 L2／L3 的一致性由\n`tests/test_batch_z66b.py` 守住。"""\n\nOPTIONAL_INPUTS: tuple[str, ...] = ("M1B_YoY_pct", "M2_YoY_pct", "BIAS240_pct", "PCR")\n"""Optional：缺時照算（缺項不計分），但未評估項必須揭露（檔案的 `not_evaluated`、步驟報告）。\nM1B／M2 另受 M1B-M2 腿停用（批 Z66）—— 停用時回報為「已停用、不計分」，不算未評估。"""\n\nREQUIRED_CORE_LABELS: Mapping[str, str] = MappingProxyType({\n    "VIX_Index": "VIX",\n    "ISM_PMI_or_OECD_CLI": "台灣 PMI 當月",\n    "PMI_Prev_Month": "台灣 PMI 前月",\n    "Futures_Net_Short": "外資期貨淨空單",\n    "Index_Below_MA5": "加權指數跌破 MA5",\n})\n"""Required Core 的客戶語言名稱（步驟報告用）。"""\n\n#: 寫進 `macro_state.json` 的「Required Core 全部可評估」戳記欄位名。\nREQUIRED_CORE_OK_KEY: str = "required_core_ok"\n\n\ndef is_valid_risk_cap_snapshot(state: Any) -> bool:\n    """這份 `macro_state.json` 內容能不能當**系統風險上限**用（新 UI／服務讀端的唯一判斷）。\n\n    兩條同時成立才算：`required_core_ok is True`（必須是 bool True，⛔ 不收 1／"true"）\n    且 `risk_cap_ruleset_version == RISK_CAP_RULESET_VERSION`（現行規則版本）。\n    舊 UI 寫的檔、批 Z66 以前的檔都沒有這兩個欄位 ⇒ False（fail-safe 方向：寧可「無法判定」）。\n    有效期限（7 天）**不在這裡判**，由 `macro_state_locker.macro_state_is_expired` 負責（同一條既有規則）。\n    """\n    if not isinstance(state, Mapping):\n        return False\n    return (state.get(REQUIRED_CORE_OK_KEY) is True\n            and state.get(RISK_CAP_RULESET_VERSION_KEY) == RISK_CAP_RULESET_VERSION)\n',
         ''),
    ),
    'src/services/ai_qa_service.py': (
        ('def _macro_state(*, require_valid_risk_cap: bool = False) -> dict:\n',
         'def _macro_state() -> dict:\n'),
        ('\n    require_valid_risk_cap（批 Z66，客戶 2026-10-16 Q1；預設 False = 既有行為一字不變）：True → 兩條來源都透傳\n    同名參數 ⇒ `exposure_limit_pct` 只認核心齊全＋現行規則版本的 `macro_state.json`。\n',
         ''),
        ('    _kw = {"require_valid_risk_cap": True} if require_valid_risk_cap else {}\n',
         ''),
        ('        return get_macro_regime(**_kw)\n',
         '        return get_macro_regime()\n'),
        ('        return get_macro_state(**_kw)\n',
         '        return get_macro_state()\n'),
        ('def _tool_get_market_state(*, require_valid_risk_cap: bool = False) -> dict:\n',
         'def _tool_get_market_state() -> dict:\n'),
        ('    # 批 Z66（Q1）：`require_valid_risk_cap=True`（新 UI 問答頁經 `run_agent` 傳入）⇒ 曝險上限只認有效快照，\n    #   且非有效快照的「鎖定快照額外欄位」（風險等級／Macro_Phase）也不附 —— 那是同一份上限的說明。\n    _ms = _macro_state(require_valid_risk_cap=True) if require_valid_risk_cap else _macro_state()\n',
         '    _ms = _macro_state()\n'),
        ('    if require_valid_risk_cap:\n        from shared.risk_cap_policy import is_valid_risk_cap_snapshot\n        if not is_valid_risk_cap_snapshot(_file):\n            _extra = {}\n',
         ''),
        ('              stop_on_invalid_number: bool = False,\n              require_valid_risk_cap: bool = False) -> QAResult:\n',
         '              stop_on_invalid_number: bool = False) -> QAResult:\n'),
        ('    require_valid_risk_cap:\n        批 Z66(客戶 2026-10-16 Q1)。True 且 `tools` 未指定 → `get_market_state` 改用\n        `_tool_get_market_state(require_valid_risk_cap=True)`:系統風險上限只認核心齊全＋現行規則版本的\n        `macro_state.json`,其餘(舊 UI 寫的、舊版本)→ `exposure_limit_pct=None`。新 UI 問答頁傳 True。\n        預設 False = 本參數出現之前的行為,一個 byte 不差(`tab_ai_chat` 不傳)。\n',
         ''),
        ('    if tools is None and require_valid_risk_cap:\n        tools = {**REAL_TOOLS,\n                 "get_market_state": lambda: _tool_get_market_state(require_valid_risk_cap=True)}\n',
         ''),
    ),
    'src/services/allocation_service.py': (
        ('def get_allocation(*, strict: bool = False,\n                   require_valid_risk_cap: bool = False) -> AllocationDecision:\n',
         'def get_allocation(*, strict: bool = False) -> AllocationDecision:\n'),
        ('\n    require_valid_risk_cap（批 Z66，客戶 2026-10-16 Q1；預設 False = 既有行為一字不變，舊 UI 不傳）：\n    True → 透傳 `get_macro_state(require_valid_risk_cap=True)`：「系統風險上限」只取自核心齊全＋現行規則版本\n    的檔；否則沒有那條 `Cap` ⇒ 新頁「建議持股：無法判定」（`src/ui/views/risk_cap_gate.py`）。\n    快取簽章本來就含 `exposure_limit_pct`，新舊 UI 同一 session 交替呼叫不會互拿對方的結果。\n',
         ''),
        ("        _kw = {'require_valid_risk_cap': True} if require_valid_risk_cap else {}\n        _ms = get_macro_state(_wr, strict=True, **_kw) if strict else get_macro_state(_wr, **_kw)\n",
         '        _ms = get_macro_state(_wr, strict=True) if strict else get_macro_state(_wr)\n'),
        ('def get_macro_regime(*, strict: bool = False, require_valid_risk_cap: bool = False) -> dict:\n',
         'def get_macro_regime(*, strict: bool = False) -> dict:\n'),
        ('\n    require_valid_risk_cap（批 Z66，客戶 2026-10-16 Q1；預設 False = 既有行為一字不變）：True → 透傳\n    `get_macro_state(require_valid_risk_cap=True)`（回傳的 `exposure_limit_pct` 只認核心齊全＋現行規則版本的檔）。\n',
         ''),
        ("    _kw = {'require_valid_risk_cap': True} if require_valid_risk_cap else {}\n",
         ''),
        ('        return get_macro_state(_wr, strict=True, **_kw)\n',
         '        return get_macro_state(_wr, strict=True)\n'),
        ('        return get_macro_state(_wr, **_kw)\n',
         '        return get_macro_state(_wr)\n'),
    ),
    'src/services/macro_engine_inputs.py': (
        ('from shared.risk_cap_policy import REQUIRED_CORE_INPUTS\n',
         ''),
        ('\n# 📌 批 Z66（客戶 2026-10-16 Q1）：系統風險上限的 Required Core `REQUIRED_CORE_INPUTS`（檔頭由 L0\n#   `shared.risk_cap_policy` import，本檔可經 `M.REQUIRED_CORE_INPUTS` 取用）緊鄰紅線表對照：\n#   外資期貨＋MA5 ＝ `RED_LINE_INPUTS[RL_FUTURES]`、PMI 當月＋前月 ＝ `RED_LINE_INPUTS[RL_PMI]`、再加 VIX。\n#   「能不能評估」用的是與 `_red_line` 同一條判定（見 `required_core_gaps`）。\n',
         ''),
        ('def required_core_gaps(bundle: "EngineInputBundle") -> tuple[tuple[str, str], ...]:\n    """Required Core 中**無法評估**的項目：`((鍵名, 「狀態（原因）」), ...)`，依 `REQUIRED_CORE_INPUTS` 順序。\n\n    判定與 `_red_line` 相同：新鮮度非 FRESH，或計分值為 None。全部可評估 ⇒ `()`。\n    （批 Z66，客戶 2026-10-16 Q1；⛔ 不另寫一套判斷。）\n    """\n    out: list[tuple[str, str]] = []\n    for k in REQUIRED_CORE_INPUTS:\n        av = bundle.assessed[k]\n        if av.verdict.status != FreshnessStatus.FRESH or av.scoring_value is None:\n            out.append((k, f"{_STATUS_TEXT[av.verdict.status]}（{av.verdict.reason}）"))\n    return tuple(out)\n\n\n',
         ''),
    ),
    'src/services/macro_refresh_service.py': (
        ('            # 批 Z66（Q1）收尾（v3 §01-2：因本次改動才變成死碼）：修前此處另有「硬否決紅線無法判定」那一句（列出 undetermined 的紅線）。\n            #   兩條硬紅線（PMI 連兩月、外資期貨＋MA5）的必要輸入全屬 Required Core，`risk_cap_apply` 的\n            #   核心閘門保證「寫得出檔 ⇒ 紅線必可評估」⇒ 那句永遠不會出現，已刪（tests/test_batch_z66b.py 守）。\n',
         '            _rl = (_rc.bundle_summary or {}).get("red_lines") or {}\n            _und = [k for k, v in _rl.items() if v == "undetermined"]\n'),
        ('                  + "；薩姆規則目前無資料來源、未評估（不代表已通過）"\n',
         '                  + (f"；硬否決紅線無法判定：{\'、\'.join(_und)}" if _und else "")\n                  + "；薩姆規則目前無資料來源、未評估（不代表已通過）"\n'),
        ('            # 批 Z66（客戶 2026-10-16 Q1）：沒寫檔時一律點名哪幾個 Required Core 無法評估、Optional 哪幾項未評估；\n            #   沿用規則改寫成「7 天內的**有效**快照」（核心齊全＋現行規則版本）—— 舊 UI 寫的、舊版本的檔新頁不認。\n            from shared.risk_cap_policy import REQUIRED_CORE_INPUTS, REQUIRED_CORE_LABELS\n            _mc = list(getattr(_rc, "missing_core", ()) or ())\n            _ne = list((_rc.bundle_summary or {}).get("not_evaluated") or ())\n            _opt_ne = [k for k in _ne if k not in REQUIRED_CORE_INPUTS]\n            _core_note = (\n                ("；Required Core 無法評估：" + "、".join(f"{REQUIRED_CORE_LABELS.get(k, k)}（{k}）" for k in _mc)\n                 + "（本輪不產生新的系統風險上限）") if _mc and not _rc.reason.startswith("Required Core") else "")\n            _opt_note = (f"；選配項未評估：{\'、\'.join(_opt_ne)}（缺項不計分）" if _opt_ne else "")\n',
         ''),
        ('                  f"{_rc.reason}" + _core_note + _opt_note\n                  + f"（既有 macro_state.json 若是 {MACRO_VERDICT_MAX_AGE_DAYS} 天有效期內的有效快照"\n                  "〔Required Core 齊全、現行規則版本〕，卡①仍沿用它的上限；過期、不存在、"\n                  "舊版或核心不齊的檔，新頁的建議持股顯示「無法判定」）"\n',
         '                  f"{_rc.reason}（既有 macro_state.json 若在 {MACRO_VERDICT_MAX_AGE_DAYS} 天有效期內，"\n                  "卡①仍沿用它的上限；過期或不存在時，新頁的建議持股顯示「無法判定」）"\n'),
    ),
    'src/services/macro_state_locker.py': (
        ('                    now=None,\n                    require_valid_risk_cap: bool = False) -> dict:\n',
         '                    now=None) -> dict:\n'),
        ('\n    require_valid_risk_cap（批 Z66，客戶 2026-10-16 Q1；預設 False = 既有行為一字不變，舊 UI 不傳）:\n      True → `exposure_limit_pct`（系統風險上限）**只**取自 `shared.risk_cap_policy.is_valid_risk_cap_snapshot`\n      為 True 的檔（`required_core_ok is True` 且規則版本＝現行）；其餘檔（舊 UI 寫的、批 Z66 以前的、\n      核心不齊的）→ `exposure_limit_pct=None`（＝沒有系統風險上限 ⇒ 新頁「建議持股：無法判定」）。\n      7 天有效期照舊由上方 `macro_state_is_expired` 判（同一條）。⚠️ 只管**上限**這一個值：\n      位階（來源優先序第 3 條）、`is_loaded`、`strict` 的拋錯判斷一律不受影響。\n      新 UI（`src/ui/views/**`）與它呼叫的服務經 `allocation_service.get_allocation(require_valid_risk_cap=True)`\n      ／`get_macro_regime(require_valid_risk_cap=True)`／`ai_qa_service.run_agent(require_valid_risk_cap=True)` 傳入。\n',
         ''),
        ('    # 批 Z36（Q-z19，客戶 2026-10-10 核准 A）：規則引擎 ~~8 項~~數值輸入**全缺**時落檔的 fail-safe（「系統異常」＋\n    #   [📌 批 Z66（客戶 2026-10-16 Q2，有意識的變更，⛔ 不是漏刪）：「全缺」自 Z66 起＝**所有啟用中的**數值輸入全缺（停用的 M1B／M2 不算）]\n',
         '    # 批 Z36（Q-z19，客戶 2026-10-10 核准 A）：規則引擎 8 項數值輸入**全缺**時落檔的 fail-safe（「系統異常」＋\n'),
        ('    if require_valid_risk_cap and _exposure is not None:\n        # 批 Z66（Q1）：只認核心齊全＋現行規則版本的檔（fail-safe 方向：認不出來 ⇒ 沒有上限 ⇒「無法判定」）\n        from shared.risk_cap_policy import is_valid_risk_cap_snapshot\n        if not is_valid_risk_cap_snapshot(_file):\n            _exposure = None\n',
         ''),
        ('      · ~~8 個**全缺**（且薩姆未觸發）→ 不計分，回既有 fail-safe `_DEFAULT_STATE` 的~~\n        ~~regime／風險／曝險／Macro_Phase（「系統異常」）＋ `missing_inputs`（批 Z34，客戶 Q-z14）。~~\n        📌 批 Z66（客戶 2026-10-16 Q2，有意識的變更，⛔ 不是漏刪）：**所有啟用中的**數值輸入全缺（且薩姆未觸發）→ 不計分，回既有 fail-safe\n        `_DEFAULT_STATE` 的 regime／風險／曝險／Macro_Phase（「系統異常」）＋ `missing_inputs`（批 Z34，\n        客戶 Q-z14）。M1B-M2 腿停用時「啟用中」＝其餘 6 項（見下段）；腿開啟時＝8 項（＝修前）。\n',
         '      · 8 個**全缺**（且薩姆未觸發）→ 不計分，回既有 fail-safe `_DEFAULT_STATE` 的\n        regime／風險／曝險／Macro_Phase（「系統異常」）＋ `missing_inputs`（批 Z34，客戶 Q-z14）。\n'),
        ('    條件重算）；~~`fail_safe=True` 只出現在「8 項數值全缺」的 fail-safe 回傳~~\n    （📌 批 Z66（客戶 2026-10-16 Q2，有意識的變更，⛔ 不是漏刪））`fail_safe=True` 只出現在「**所有啟用中的**數值輸入全缺」的 fail-safe 回傳 —— 此時三條一律 False，\n',
         '    條件重算）；`fail_safe=True` 只出現在「8 項數值全缺」的 fail-safe 回傳 —— 此時三條一律 False，\n'),
        ('    # 批 Z34（Z9-n2，客戶 2026-10-10 Q-z14＝A）：~~8 項~~數值輸入**全缺**時，下方計分只剩中性基準 60，\n',
         '    # 批 Z34（Z9-n2，客戶 2026-10-10 Q-z14＝A）：8 項數值輸入**全缺**時，下方計分只剩中性基準 60，\n'),
    ),
    'src/services/risk_cap_apply.py': (
        ('判定（三條任一成立；批 Z66 加第 3 條，見下）：\n',
         '判定（兩條任一成立）：\n'),
        ('  2. `exposure_limit_pct` 不是有限數（含 bool）；\n  3. 批 Z66（客戶 2026-10-16 Q1）：**Required Core**（L0 `shared.risk_cap_policy.REQUIRED_CORE_INPUTS`：\n     VIX、台灣 PMI 當月、台灣 PMI 前月、外資期貨淨空單＋加權指數跌破 MA5）任一無法評估 ⇒\n     本輪**不產生新的系統風險上限**（`REASON_CORE_MISSING`，點名缺的核心項）。引擎本身的「缺項不計分」\n     計算不改（Q1 是「能不能產生新上限」的閘門，不是引擎變更）；Optional（M1B／M2、PCR、BIAS240）\n     缺時照寫、`not_evaluated` 揭露。核心齊全才寫，並蓋 `required_core_ok: True`＋規則版本 ——\n     新 UI 讀端（`get_macro_state(require_valid_risk_cap=True)`）只認這種檔。\n',
         '  2. `exposure_limit_pct` 不是有限數（含 bool）。\n'),
        ('from shared.risk_cap_policy import REQUIRED_CORE_LABELS, REQUIRED_CORE_OK_KEY\n',
         ''),
        ('    required_core_gaps,\n',
         ''),
        ('                                  RISK_CAP_RULESET_VERSION_KEY, REQUIRED_CORE_OK_KEY)\n',
         '                                  RISK_CAP_RULESET_VERSION_KEY)\n'),
        ('#: 批 Z66（Q1）：Required Core 缺 ⇒ 不產生新上限。`{items}` ＝ 缺的核心項（客戶語言名稱＋鍵名＋狀態）。\nREASON_CORE_MISSING: str = (\n    "Required Core 無法評估：{items} → 本輪不產生新的系統風險上限，不寫檔（既有檔若有，保留不動）")\n',
         ''),
        ('        missing_core: 批 Z66（Q1）：無法評估的 Required Core 鍵名（依 `REQUIRED_CORE_INPUTS` 順序；\n            核心齊全 ⇒ `()`）。不論有沒有寫檔都照實帶（fail-safe 時通常也是全缺）。\n',
         ''),
        ('    missing_core: tuple[str, ...] = ()\n',
         ''),
        ('def _core_items_text(gaps: tuple[tuple[str, str], ...]) -> str:\n    """`required_core_gaps` → 「VIX（VIX_Index：未取得（…））、…」。"""\n    return "、".join(f"{REQUIRED_CORE_LABELS.get(k, k)}（{k}：{why}）" for k, why in gaps)\n\n\n',
         ''),
        ('    gaps = required_core_gaps(bundle)\n    missing_core = tuple(k for k, _ in gaps)\n',
         ''),
        ('        return RiskCapApplyResult(False, REASON_FAIL_SAFE, summary, engine, missing_core)\n',
         '        return RiskCapApplyResult(False, REASON_FAIL_SAFE, summary, engine)\n'),
        ('        return RiskCapApplyResult(False, why, summary, engine, missing_core)\n    # 批 Z66（客戶 2026-10-16 Q1）：Required Core 任一無法評估 ⇒ 不產生新上限、不寫檔（⛔ 不因缺資料放寬風控）。\n    #   排在 fail-safe／非有限數之後：那兩條是「引擎根本沒給出可用上限」，原因照舊報；本條是「給得出、但不准用」。\n    if gaps:\n        why = REASON_CORE_MISSING.format(items=_scrub_nonfinite_text(_core_items_text(gaps)))\n        print(f"[risk_cap_apply] ⚠️ {why}")\n        return RiskCapApplyResult(False, why, summary, engine, missing_core)\n',
         '        return RiskCapApplyResult(False, why, summary, engine)\n'),
        ('    payload[REQUIRED_CORE_OK_KEY] = True     # 批 Z66（Q1）：走到這裡 ⇔ Required Core 全部可評估\n',
         ''),
    ),
    'src/ui/views/page_hold.py': (
        ('        # 批 Z66（客戶 2026-10-16 Q1）：系統風險上限只認核心齊全＋現行規則版本的 `macro_state.json`\n        #   （舊 UI 寫的、舊版本的檔 ⇒ 沒有上限 ⇒ 建議持股「無法判定」）。\n        _a = get_allocation(strict=True, require_valid_risk_cap=True)\n',
         '        _a = get_allocation(strict=True)\n'),
    ),
    'src/ui/views/page_today.py': (
        ('        # 批 Z66（客戶 2026-10-16 Q1）：系統風險上限只認核心齊全＋現行規則版本的 `macro_state.json`\n        #   （舊 UI 寫的、舊版本的檔 ⇒ 沒有上限 ⇒ 建議持股「無法判定」）。\n        return get_allocation(require_valid_risk_cap=True), ""\n',
         '        return get_allocation(), ""\n'),
        ('        # 批 Z66（客戶 2026-10-16 Q1）：系統風險上限只認核心齊全＋現行規則版本的 `macro_state.json`\n        #   （卡①未評估時的說明句讀 `exposure_limit_pct`，須與卡①同一個判斷）。\n        return get_macro_regime(require_valid_risk_cap=True), ""\n',
         '        return get_macro_regime(), ""\n'),
    ),
    'src/ui/views/page_why.py': (
        ('        # 批 Z66（客戶 2026-10-16 Q1）：`require_valid_risk_cap=True` —— 問答工具回報的系統風險上限\n        #   只認核心齊全＋現行規則版本的 `macro_state.json`（與今天頁卡①同一條判斷）。\n',
         ''),
        ('                         fail_on_blocked_reply=True, stop_on_invalid_number=True,\n                         require_valid_risk_cap=True)\n',
         '                         fail_on_blocked_reply=True, stop_on_invalid_number=True)\n'),
    ),
}
# ── 還原組結束 ──


def z66b_revert_for(file_path, code: str, *, only=None, skip=()) -> str:
    """舊批次還原鏈串接用：給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣）。

    `only`／`skip`：限定（或排除）要還原的檔。`tests/test_batch_z56.py::z56_revert_for` 只還原
    `Z66B_VIA_Z56`（它那條鏈管的檔），`tests/test_batch_z66.py::z66_revert_for` 排除它們 ——
    `test_batch_z34.z34_revert` 對 'qa' 兩條鏈都會走，各還原一次會因替換點已不存在而炸。
    """
    p = Path(file_path)
    rel = (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()
    if (only is not None and rel not in only) or rel in skip:
        return code
    for new, old in Z66B_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def z66b_pairs_for(file_path) -> tuple:
    """給模組 `__file__`（或 repo 相對路徑），回本批該檔的還原組（無則空 tuple；供以 pair 清單串接的舊測試用）。"""
    p = Path(file_path)
    rel = (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()
    return Z66B_REVERT_PAIRS.get(rel, ())


@__import__("pytest").mark.parametrize("rel", sorted(Z66B_REVERT_PAIRS))
def test_z66b_revert_is_exact_base_source(rel):
    code = z66b_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z66B_BASE_SHA[rel]


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案與舊批次測試
# ══════════════════════════════════════════════════════════════════════════
import ast  # noqa: E402
import re  # noqa: E402
import json  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402

from shared import risk_cap_policy as RP  # noqa: E402
from src.compute.macro import dated_inputs as DI  # noqa: E402
from src.services import macro_engine_inputs as M  # noqa: E402
from src.services import macro_refresh_service as RS  # noqa: E402
from src.services import macro_state_locker as MSL  # noqa: E402
from src.services import risk_cap_apply as RC  # noqa: E402
from src.services.macro_state_locker import get_macro_state  # noqa: E402
from tests.test_batch_z64 import NOW, _build, _inputs, _session_from  # noqa: E402
from tests.test_batch_z65 import (  # noqa: E402,F401
    _WR_LIVE, _as_session, _run_refresh, _step, _write_old_valid_file, l1)
from tests.test_p01_macro_refresh import _mutated_module  # noqa: E402

TPE = timezone(timedelta(hours=8))
_CORE = RP.REQUIRED_CORE_INPUTS

#: 每個核心項「單獨無法評估」的輸入寫法（其餘完整且新鮮）。
_CORE_ALONE = {
    "VIX_Index": dict(vix=None),
    "ISM_PMI_or_OECD_CLI": dict(pmi=float("nan")),     # 當期缺 ⇒ 前月也跟著無法定錨（見下方斷言）
    "PMI_Prev_Month": dict(prev_month=None),
    "Futures_Net_Short": dict(fut=float("nan")),
    "Index_Below_MA5": dict(below=None),
}


def _stamped(data: dict, *, ok=True, version=RP.RISK_CAP_RULESET_VERSION) -> dict:
    out = dict(data)
    if ok is not None:
        out[RP.REQUIRED_CORE_OK_KEY] = ok
    if version is not None:
        out[RP.RISK_CAP_RULESET_VERSION_KEY] = version
    return out


def _file(path: Path, *, days_ago: float, cap: int = 30, **stamp) -> bytes:
    data = {"market_regime": "空頭", "systemic_risk_level": "危險", "exposure_limit_pct": cap,
            "Macro_Phase": "環境正常", "analysis_summary": f"曝險上限 {cap}%（Python 規則引擎計算）",
            "timestamp": (NOW - timedelta(days=days_ago)).astimezone(TPE).strftime(MSL._TIMESTAMP_FMT)}
    if stamp.pop("stamp", True):
        data = _stamped(data, **stamp)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
    return path.read_bytes()


# ══════════════════════════════════════════════════════════════════════════
# 1. L0 SSOT
# ══════════════════════════════════════════════════════════════════════════
class TestPolicy:
    def test_core_and_optional_partition_engine_inputs(self):
        assert _CORE == ("VIX_Index", "ISM_PMI_or_OECD_CLI", "PMI_Prev_Month",
                         "Futures_Net_Short", "Index_Below_MA5")
        assert set(_CORE).isdisjoint(RP.OPTIONAL_INPUTS)
        assert set(_CORE) | set(RP.OPTIONAL_INPUTS) == set(M.ENGINE_INPUT_KEYS)
        assert set(RP.REQUIRED_CORE_LABELS) == set(_CORE)
        for k in _CORE + RP.OPTIONAL_INPUTS:            # 與 L2 抽取器同一份鍵名
            assert k in DI.COVERED_ENGINE_INPUTS, k

    def test_core_pairs_are_the_red_line_pairs(self):
        assert M.RED_LINE_INPUTS[M.RL_FUTURES] == ("Futures_Net_Short", "Index_Below_MA5")
        assert set(M.RED_LINE_INPUTS[M.RL_FUTURES]) <= set(_CORE)
        assert set(M.RED_LINE_INPUTS[M.RL_PMI]) <= set(_CORE)
        assert M.REQUIRED_CORE_INPUTS is RP.REQUIRED_CORE_INPUTS

    def test_l0_has_no_l1_plus_import(self):
        tree = ast.parse((REPO / "shared/risk_cap_policy.py").read_text(encoding="utf-8"))
        mods = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        mods += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert all(m in ("__future__", "types", "typing") or m.startswith("shared") for m in mods), mods

    @pytest.mark.parametrize("state,ok", [
        ({"required_core_ok": True, "risk_cap_ruleset_version": "risk_cap.v2"}, True),
        ({"required_core_ok": True}, False),
        ({"risk_cap_ruleset_version": "risk_cap.v2"}, False),
        ({"required_core_ok": 1, "risk_cap_ruleset_version": "risk_cap.v2"}, False),
        ({"required_core_ok": "true", "risk_cap_ruleset_version": "risk_cap.v2"}, False),
        ({"required_core_ok": False, "risk_cap_ruleset_version": "risk_cap.v2"}, False),
        ({"required_core_ok": True, "risk_cap_ruleset_version": "risk_cap.v1"}, False),
        ({}, False), (None, False), ("x", False)])
    def test_is_valid_snapshot(self, state, ok):
        assert RP.is_valid_risk_cap_snapshot(state) is ok

    def test_core_gaps_same_predicate_as_red_lines(self):
        for k, kw in _CORE_ALONE.items():
            b = _build(_inputs(**kw))
            gaps = dict(M.required_core_gaps(b))
            assert k in gaps, (k, gaps)
            assert set(gaps) == {c for c in _CORE if c in b.not_evaluated}, k
            for name, keys in M.RED_LINE_INPUTS.items():
                if name == M.RL_SAHM:
                    continue
                assert (b.red_lines[name].status == "undetermined") == any(x in gaps for x in keys)
        assert M.required_core_gaps(_build(_inputs())) == ()


# ══════════════════════════════════════════════════════════════════════════
# 2. 寫端：Required Core 閘門
# ══════════════════════════════════════════════════════════════════════════
class TestWriteGate:
    @pytest.mark.parametrize("key", list(_CORE_ALONE))
    def test_each_core_missing_alone_not_written(self, l1, tmp_path, key):
        kw = _inputs(**_CORE_ALONE[key])
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        before = _file(f, days_ago=3, cap=30)
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        assert not res.written and key in res.missing_core
        assert res.reason.startswith("Required Core 無法評估：")
        assert f"{RP.REQUIRED_CORE_LABELS[key]}（{key}：" in res.reason
        assert "本輪不產生新的系統風險上限，不寫檔（既有檔若有，保留不動）" in res.reason
        assert f.read_bytes() == before and not (tmp_path / "macro_state.json.tmp").exists()
        # 引擎本身照常算（Q1 是閘門，不是引擎變更）：給得出上限，只是不准用
        assert res.engine_result["veto_flags"]["fail_safe"] is False
        assert isinstance(res.engine_result["exposure_limit_pct"], int)
        # 7 天內的有效舊檔照舊被新 UI 讀到
        assert get_macro_state(None, state_file_path=str(f), now=NOW,
                               require_valid_risk_cap=True)["exposure_limit_pct"] == 30
        if key == "ISM_PMI_or_OECD_CLI":
            assert res.missing_core == ("ISM_PMI_or_OECD_CLI", "PMI_Prev_Month")
        else:
            assert res.missing_core == (key,)

    def test_vix_only_not_written(self, l1, tmp_path):
        l1(None)
        f = tmp_path / "macro_state.json"
        res = RC.compute_and_lock_risk_cap({"macro_info": {"vix": {"current": 17.3, "date": "2026-10-13"}}},
                                           now=NOW, state_file_path=str(f))
        assert not res.written and not f.exists()
        assert res.missing_core == ("ISM_PMI_or_OECD_CLI", "PMI_Prev_Month", "Futures_Net_Short",
                                    "Index_Below_MA5")
        assert res.engine_result["exposure_limit_pct"] == 60   # 修前（Z65）會把這個 60 寫進檔

    def test_core_ok_optional_missing_written_and_stamped(self, l1, tmp_path):
        kw = _inputs(bias=None, pcr=float("nan"), m1b=None, m2=None)
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        assert res.written and res.missing_core == ()
        state = json.loads(f.read_text(encoding="utf-8"))
        assert state[RP.REQUIRED_CORE_OK_KEY] is True
        assert state[RP.RISK_CAP_RULESET_VERSION_KEY] == RP.RISK_CAP_RULESET_VERSION
        assert set(state["not_evaluated"]) == {"BIAS240_pct", "PCR"}
        assert state["disabled_inputs"] == ["M1B_YoY_pct", "M2_YoY_pct"]
        assert RP.is_valid_risk_cap_snapshot(state)
        assert get_macro_state(None, state_file_path=str(f),
                               require_valid_risk_cap=True)["exposure_limit_pct"] == state["exposure_limit_pct"]

    def test_full_inputs_written(self, l1, tmp_path):
        kw = _inputs()
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f))
        assert res.written and json.loads(f.read_text(encoding="utf-8"))["required_core_ok"] is True
        assert RP.REQUIRED_CORE_OK_KEY in RC.ATTACHED_KEYS

    def test_fail_safe_reports_missing_core(self, l1, tmp_path):
        res = RC.compute_and_lock_risk_cap({}, now=NOW, state_file_path=str(tmp_path / "m.json"))
        assert not res.written and res.reason == RC.REASON_FAIL_SAFE
        assert res.missing_core == _CORE


# ══════════════════════════════════════════════════════════════════════════
# 3. 讀端：新 UI 只認有效快照
# ══════════════════════════════════════════════════════════════════════════
class TestReadSide:
    @pytest.mark.parametrize("kind,days,stamp,expect", [
        ("old_ui_unstamped", 1.0, dict(stamp=False), None),
        ("old_version", 1.0, dict(version="risk_cap.v1"), None),
        ("no_core_flag", 1.0, dict(ok=None), None),
        ("core_flag_false", 1.0, dict(ok=False), None),
        ("valid_6_9d", 6.9, {}, 30),
        ("valid_7_1d", 7.1, {}, None),
    ])
    def test_get_macro_state(self, tmp_path, kind, days, stamp, expect):
        f = tmp_path / "macro_state.json"
        _file(f, days_ago=days, cap=30, **stamp)
        got = get_macro_state(None, state_file_path=str(f), now=NOW, require_valid_risk_cap=True)
        assert got["exposure_limit_pct"] == expect, kind
        # 預設（舊 UI 呼叫方式）：一字不變 —— 未過期的檔照舊給上限
        legacy = get_macro_state(None, state_file_path=str(f), now=NOW)
        assert legacy["exposure_limit_pct"] == (None if days > 7 else 30), kind
        # 只動上限：位階／is_loaded 與預設相同
        assert {k: v for k, v in got.items() if k != "exposure_limit_pct"} == \
               {k: v for k, v in legacy.items() if k != "exposure_limit_pct"}

    def test_strict_unaffected(self, tmp_path):
        f = tmp_path / "macro_state.json"
        _file(f, days_ago=1.0, stamp=False)
        a = get_macro_state(None, state_file_path=str(f), now=NOW, strict=True,
                            require_valid_risk_cap=True)
        assert a["exposure_limit_pct"] is None and a["is_loaded"] and "file_error" not in a

    @pytest.fixture
    def fresh(self, monkeypatch, tmp_path):
        """cwd＝tmp、真實時鐘：寫一份**現在**的檔（`get_allocation` 不收 now）。"""
        monkeypatch.chdir(tmp_path)

        def _write(**stamp):
            f = tmp_path / "macro_state.json"
            data = {"market_regime": "空頭", "systemic_risk_level": "危險", "exposure_limit_pct": 30,
                    "Macro_Phase": "環境正常", "timestamp": MSL._now_str()}
            if stamp.pop("stamp", True):
                data = _stamped(data, **stamp)
            f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return _write

    @pytest.mark.parametrize("stamp,has_cap", [(dict(stamp=False), False), (dict(version="v0"), False),
                                               ({}, True)])
    def test_new_ui_pages(self, fresh, monkeypatch, stamp, has_cap):
        from src.ui.views import page_hold as PH
        from src.ui.views import page_today as P
        from src.ui.views.risk_cap_gate import has_system_risk_cap
        fresh(**stamp)
        AS = _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        alloc, err = P._load_allocation()
        regime, rerr = P._load_regime()
        assert not err and not rerr and alloc.is_loaded
        assert has_system_risk_cap(alloc.caps) is has_cap
        assert (regime["exposure_limit_pct"] == 30) is has_cap
        tiles = {t.card.key: t for t in P.build_verdict_tiles(
            alloc=alloc, alloc_error="", danger=None, danger_error="",
            danger_requested=False, regime=regime, regime_error="")}
        c = tiles["verdict.exposure"].card
        if has_cap:
            assert c.state == P.UI_LIVE
        else:
            assert c.state == P.UI_EMPTY and "無法判定" in c.note.now
        card, _, _ = PH.build_position_cap_card(PH.load_allocation(PH.HoldRequest(submitted=True)))
        assert (card.state == PH.UI_LIVE) is has_cap
        if not has_cap:
            assert card.note.now == PH.RISK_CAP_UNAVAILABLE_NOW
        # 舊 UI 的呼叫方式（不傳參數）一字不變：同一份檔照舊有上限
        assert has_system_risk_cap(AS.get_allocation().caps)

    def test_ai_qa(self, fresh, monkeypatch):
        from src.services import ai_qa_service as Q
        fresh(stamp=False)
        _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        legacy = Q._tool_get_market_state()
        new = Q._tool_get_market_state(require_valid_risk_cap=True)
        assert legacy["data"]["exposure_limit_pct"] == 30
        assert "鎖定快照額外欄位_macro_state_json" in legacy["data"]
        assert new["data"]["exposure_limit_pct"] is None
        assert "鎖定快照額外欄位_macro_state_json" not in new["data"]
        fresh()
        assert Q._tool_get_market_state(require_valid_risk_cap=True)["data"]["exposure_limit_pct"] == 30

    def test_run_agent_opt_in_routes_tool(self, fresh, monkeypatch):
        from src.services import ai_qa_service as Q
        fresh(stamp=False)
        _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        for flag, expect in ((True, None), (False, 30)):
            calls = iter([{"candidates": [{"content": {"parts": [
                {"functionCall": {"name": "get_market_state", "args": {}}}]}}]},
                {"candidates": [{"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}]}])
            res = Q.run_agent("q", gemini_http=lambda payload: next(calls),
                              require_valid_risk_cap=flag)
            (tc,) = res.tool_calls
            assert tc["result"]["data"]["exposure_limit_pct"] == expect, flag

    def test_new_ui_call_sites_opt_in_and_old_ui_does_not(self):
        """AST：真的以 `require_valid_risk_cap=True` 呼叫的檔 —— 只有新 UI 頁與服務內的透傳；舊 UI 0 處。"""
        hits = set()
        for p in list((REPO / "src").rglob("*.py")) + [REPO / "app.py"]:
            for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
                if isinstance(n, ast.Call) and any(
                        kw.arg == "require_valid_risk_cap"
                        and isinstance(kw.value, ast.Constant) and kw.value.value is True
                        for kw in n.keywords):
                    hits.add(p.relative_to(REPO).as_posix())
        assert hits == {"src/ui/views/page_today.py", "src/ui/views/page_hold.py",
                        "src/ui/views/page_why.py", "src/services/ai_qa_service.py"}, hits
        assert not any(h.startswith("src/ui/tabs") or h == "app.py" for h in hits)


# ══════════════════════════════════════════════════════════════════════════
# 4. 步驟報告（既有元素，只改文字）
# ══════════════════════════════════════════════════════════════════════════
class TestRefreshReport:
    def test_core_missing_report(self, monkeypatch, tmp_path):
        kw = _inputs(prev_month=None, bias=None)
        before = _file(tmp_path / "macro_state.json", days_ago=3)
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                               pmi_hist=kw["pmi_history"])
        s = _step(r, RS.STEP_RISK_CAP)
        assert s.ok and s.skipped
        assert "Required Core 無法評估：台灣 PMI 前月（PMI_Prev_Month：" in s.detail
        assert "本輪不產生新的系統風險上限" in s.detail
        assert "7 天有效期內的有效快照" in s.detail and "新頁的建議持股顯示「無法判定」" in s.detail
        assert "選配項未評估：BIAS240_pct（缺項不計分）" in s.detail
        assert "M1B-M2 資金活水已停用、不計分" in s.detail
        assert (tmp_path / "macro_state.json").read_bytes() == before

    def test_fail_safe_report_names_core(self, monkeypatch, tmp_path):
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session={})
        s = _step(r, RS.STEP_RISK_CAP)
        assert s.skipped and RC.REASON_FAIL_SAFE in s.detail
        assert "Required Core 無法評估：VIX（VIX_Index）" in s.detail

    def test_written_report_unchanged_shape(self, monkeypatch, tmp_path):
        kw = _inputs(bias=None)
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                               pmi_hist=kw["pmi_history"])
        s = _step(r, RS.STEP_RISK_CAP)
        assert s.ok and not s.skipped and "已寫入 macro_state.json" in s.detail
        assert "未評估 1 項（BIAS240_pct；缺項不計分）" in s.detail


# ══════════════════════════════════════════════════════════════════════════
# 5. 突變自驗（恰一次字面替換 → 守衛必須轉紅）
# ══════════════════════════════════════════════════════════════════════════
class TestMutations:
    def test_gate_removed_writes_vix_only(self, l1, tmp_path):
        mod = _mutated_module("src/services/risk_cap_apply.py", ("    if gaps:\n", "    if False:\n"))
        l1(None)
        f = tmp_path / "macro_state.json"
        before = _file(f, days_ago=3)
        sess = {"macro_info": {"vix": {"current": 17.3, "date": "2026-10-13"}}}
        assert not RC.compute_and_lock_risk_cap(sess, now=NOW, state_file_path=str(f)).written
        assert f.read_bytes() == before
        assert mod.compute_and_lock_risk_cap(sess, now=NOW, state_file_path=str(f)).written
        assert f.read_bytes() != before          # 突變體蓋掉舊檔 ⇒ 原版的 bytes 守衛抓得到

    def test_read_side_check_removed(self, tmp_path):
        mod = _mutated_module("src/services/macro_state_locker.py",
                              ("        if not is_valid_risk_cap_snapshot(_file):\n",
                               "        if False:\n"))
        f = tmp_path / "macro_state.json"
        _file(f, days_ago=1.0, stamp=False)
        assert get_macro_state(None, state_file_path=str(f), now=NOW,
                               require_valid_risk_cap=True)["exposure_limit_pct"] is None
        assert mod.get_macro_state(None, state_file_path=str(f), now=NOW,
                                   require_valid_risk_cap=True)["exposure_limit_pct"] == 30

    def test_stamp_removed_valid_file_unreadable(self, l1, tmp_path):
        """突變：寫端不蓋戳 ⇒ 新 UI 連剛寫的有效檔都不認（證明讀寫兩端的戳記是同一份）。"""
        mod = _mutated_module("src/services/risk_cap_apply.py", (
            "    payload[REQUIRED_CORE_OK_KEY] = True", "    pass"))
        kw = _inputs()
        l1(kw["pmi_history"])
        f = tmp_path / "macro_state.json"
        assert mod.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(f)).written
        assert get_macro_state(None, state_file_path=str(f),
                               require_valid_risk_cap=True)["exposure_limit_pct"] is None

    def test_page_call_site_opt_in_removed(self, monkeypatch, tmp_path):
        mod = _mutated_module("src/ui/views/page_today.py", (
            "        return get_allocation(require_valid_risk_cap=True), \"\"",
            "        return get_allocation(), \"\""))
        monkeypatch.chdir(tmp_path)
        (tmp_path / "macro_state.json").write_text(json.dumps(
            {"market_regime": "空頭", "systemic_risk_level": "危險", "exposure_limit_pct": 30,
             "Macro_Phase": "環境正常", "timestamp": MSL._now_str()}, ensure_ascii=False), encoding="utf-8")
        _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        from src.ui.views import page_today as P
        from src.ui.views.risk_cap_gate import has_system_risk_cap
        assert not has_system_risk_cap(P._load_allocation()[0].caps)
        assert has_system_risk_cap(mod._load_allocation()[0].caps)   # 突變體認了舊 UI 的檔 ⇒ 原版守衛必紅


# ══════════════════════════════════════════════════════════════════════════
# 6. 收尾（v3 §01-2）：寫得出檔 ⇒ 紅線必可評估；步驟報告「紅線無法判定」那句已刪
# ══════════════════════════════════════════════════════════════════════════
class TestWrittenNeverUndetermined:
    @pytest.mark.parametrize("kw", [{}, dict(bias=None), dict(pcr=float("nan")), dict(m1b=None, m2=None),
                                    dict(bias=float("nan"), pcr=float("nan"), m1b=float("nan"))]
                             + [v for v in _CORE_ALONE.values()])
    def test_written_has_no_undetermined_red_line(self, l1, tmp_path, kw):
        k = _inputs(**kw)
        l1(k["pmi_history"])
        f = tmp_path / "macro_state.json"
        res = RC.compute_and_lock_risk_cap(_session_from(k), now=NOW, state_file_path=str(f))
        und = [n for n, s in res.bundle_summary["red_lines"].items() if s == "undetermined"]
        if res.written:
            assert und == [], (kw, und)
            st = json.loads(f.read_text(encoding="utf-8"))
            assert all(v["status"] != "undetermined" for v in st["red_lines"].values())
        else:
            assert res.missing_core             # 沒寫 ⇔ 核心缺（含所有「紅線無法判定」的情境）
        if und:
            assert not res.written, (kw, und)   # 反向自證：有紅線無法判定的情境一律被擋下

    def test_report_clause_removed(self):
        src = (REPO / "src/services/macro_refresh_service.py").read_text(encoding="utf-8")
        assert "硬否決紅線無法判定：" not in src and not re.search(r"\b_und\b", src)
