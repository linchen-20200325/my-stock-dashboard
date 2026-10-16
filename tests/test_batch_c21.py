"""AUD-C21 ＋ PQ-C6-3 —— 新 UI 自己的系統風險上限快照檔 ＋ 卡面資料完整性揭露（客戶 2026-10-16 裁示）。

客戶裁示（逐意轉錄）：
- AUD-C21：新 UI 另開獨立的 Risk Cap 快照檔；舊 UI 照舊用原檔、不改。舊 UI 寫入不得再蓋掉新 UI 的有效快照。
  新 UI 只收通過 Required Core、版本戳記、新鮮度的快照。歷史決策與凍結驗證不改寫。拆檔後逐條檢查新 UI 的讀寫
  路徑，不得還有任何退回讀舊檔上限的路。
- PQ-C6-3（線框已核准）：今天頁卡①與持股頁卡⑤，有系統風險上限時**卡面**揭露 Optional 完整性 ——
  缺項 ⇒「未評估：PCR、BIAS240」＋「部分訊號未納入，本次上限資訊不完整」（⛔ 不寫「上限可能偏寬」）；
  全有 ⇒「必要與選用訊號皆已評估」。M1B−M2 已停用，⛔ 永不列在未評估（詳細可列「已停用：M1B−M2」）。
  顏色不是唯一載體。無上限的「建議持股：無法判定」那一態不變。

守：
0. 還原鏈：本批改動換回 3dfad58d（AUD-C21 之前）的寫法（sha 寫死；`z66b_revert_for` 串本表）。
1. 覆寫回歸：新 UI 寫完後舊 UI 寫一次 ⇒ 新 UI 的上限照舊、舊 UI 的 `get_allocation()` 與修前一致。
2. 位階矩陣：warroom {無, live, 無健康分} × 檔 {只舊, 只新, 都有, 都沒有} × strict {F, T} ⇒ 上限以外逐鍵同修前。
3. 無退路：新檔缺／過期／未蓋戳／版本不符 ⇒ 沒有上限（舊檔有效也不認）；新檔壞＋strict ⇒ `file_error`（紅）。
4. 雙寫：一次刷新兩個檔逐位元組相同；閘門擋下 ⇒ 兩個都不寫；第二個寫失敗 ⇒ 第一個還原。
   新 UI 單獨使用時位階仍有第 3 順位來源（沒有雙寫就會變「未評估」）。
5. 揭露：PCR 缺／BIAS240 缺／兩者缺／全有；M1B 永不在未評估；薩姆只在詳細；缺項不給日期；
   只換 `not_evaluated` 時快取給新的揭露；無上限時不揭露。
6. 突變（各自必紅）：讀端退回舊檔、拿掉雙寫、拿掉有效判斷、揭露列出 M1B、快取簽章少了揭露。
L1 一律 mock；不連網。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原鏈（同 Z62／Z65／Z66／Z66b 慣例）：把本批改動換回 3dfad58d（AUD-C21 之前）的寫法
#    ⚠️ 本段必須在任何 `from tests...` import 之前（舊批次測試檔會回頭 import 這裡）
# ══════════════════════════════════════════════════════════════════════════
# ── 還原組（自動產生：逐段 (現行, 修前)；⛔ 手改會讓 sha 對不上）──
#: 3dfad58d 的原檔 sha256（`git show 3dfad58d:<rel> | sha256sum`；寫死以免測試依賴 git）。
# @@C21_PAIRS_BEGIN@@
C21_BASE_SHA = {
    'shared/allocation_decision.py': 'a1b522f9a25b44ece83149a027a14bef8228c24d385274a34a588c6035da0dbb',
    'shared/risk_cap_policy.py': '55e7b869c9776fe4935964d934253d9e986dba1c367baa8d62ddd001a411538e',
    'src/services/ai_qa_service.py': 'a3287dd3e37f8963e4cd34a04b053be980083089974b42b54785d74e7d5f0fc5',
    'src/services/allocation_service.py': 'f095057f98903f3608597171daf94ac4166523397fc707fb8379ba7205d1f4ac',
    'src/services/macro_refresh_service.py': '55d13354f93c48e77b716b5b554447f9b911aa9f9033d3cf0932429c7edba0a2',
    'src/services/macro_state_locker.py': '157b190d9a39fbf05fcc64761ac7322d8957df069efaa416a2ba92d5fb262299',
    'src/services/risk_cap_apply.py': 'be6f957790c7a114d76a20c2e9d374606d31855993bd903119a411f655e211de',
    'src/ui/views/page_hold.py': 'ff8c8e0972cf1ca3e51c40d0cd6fefc2ec813cf0a429f40f3e5659d8f19e57a3',
    'src/ui/views/page_today.py': '154817fd126b3910ba01e35c25489f8fe128e5045c6b3230f67f9913796741ca',
    'src/ui/views/risk_cap_gate.py': '7dbab4306614fdbe18120ac1d583d0aa5ce95c7724364eff072b1fcb5d782d67',
}
C21_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    'shared/allocation_decision.py': (
        ('from dataclasses import dataclass\nfrom typing import Any, Iterable, Sequence\n\n',
         'from dataclasses import dataclass\nfrom typing import Iterable, Sequence\n\n'),
        ('        conflicts:   與最終結論相反、但被壓制的訊號(要顯示，不要藏)\n        risk_cap_disclosure: AUD-C21／PQ-C6-3（2026-10-16）：「系統風險上限」那條 `Cap` 的資料完整性揭露\n                     （`shared.risk_cap_policy.RiskCapDisclosure`），由 `macro_state[\'risk_cap_disclosure\']`\n                     原樣帶入；**只有**那條 Cap 真的進了 `caps` 才有值，否則 None。舊 UI（不傳旗標）恆為 None。\n                     刻意放最後一欄、有預設值 ⇒ 既有建構（全部 keyword-only）一個都不用改。\n    """\n',
         '        conflicts:   與最終結論相反、但被壓制的訊號(要顯示，不要藏)\n    """\n'),
        ('    conflicts: tuple[str, ...] = ()\n    risk_cap_disclosure: Any = None\n\n',
         '    conflicts: tuple[str, ...] = ()\n\n'),
        ("    _sys_cap = _ms.get('exposure_limit_pct')\n    _disclosure = None   # AUD-C21／PQ-C6-3：只跟著「系統風險上限」那條 Cap 走\n    if _sys_cap is not None:\n",
         "    _sys_cap = _ms.get('exposure_limit_pct')\n    if _sys_cap is not None:\n"),
        ("                             else SYSTEM_RISK_CAP_BASIS_LEG_OFF))\n            _disclosure = _ms.get('risk_cap_disclosure')\n\n",
         '                             else SYSTEM_RISK_CAP_BASIS_LEG_OFF))\n\n'),
        ('        drivers=tuple(_drivers), conflicts=tuple(conflicts),\n        risk_cap_disclosure=_disclosure,\n    )\n',
         '        drivers=tuple(_drivers), conflicts=tuple(conflicts),\n    )\n'),
    ),
    'shared/risk_cap_policy.py': (
        ('from types import MappingProxyType\nfrom typing import Any, Mapping, NamedTuple\n\n',
         'from types import MappingProxyType\nfrom typing import Any, Mapping\n\n'),
        ('            and state.get(RISK_CAP_RULESET_VERSION_KEY) == RISK_CAP_RULESET_VERSION)\n\n\n# ══════════════════════════════════════════════════════════════════════════\n# AUD-C21（客戶 2026-10-16 裁示）：新 UI 自己的系統風險上限快照檔\n# ══════════════════════════════════════════════════════════════════════════\nRISK_CAP_STATE_FILE: str = "risk_cap_state.json"\n"""新 UI 的系統風險上限快照檔（相對路徑，與 `macro_state.json` 同一個工作目錄）。\n\n為什麼另開一個檔：舊 UI（`src/ui/tabs/macro/section_news_ai.py`，凍結）每次按「執行 AI 裁決」都經\n`MacroStateLocker()` **整份覆寫** `macro_state.json`（兩個戳記一起被洗掉）⇒ 新 UI 剛寫好的有效快照會被\n舊 UI 一次寫入蓋成「不認得的檔」。客戶裁示：新 UI 用自己的檔，舊 UI 照舊用原檔、一個字都不改。\n\n- 寫端：`src/services/risk_cap_apply.compute_and_lock_risk_cap` **先寫本檔、再寫 `macro_state.json`**\n  （同一份內容；`macro_state.json` 仍是舊 UI 的上限來源與 `get_macro_state()` 位階的第 3 順位來源 ——\n  位階行為屬 AUD-C22，本批不動，故雙寫）。舊 UI 只寫 `macro_state.json`，**碰不到本檔**。\n- 讀端：`macro_state_locker.get_macro_state(require_valid_risk_cap=True)` 的 `exposure_limit_pct`\n  **只**取自本檔（Required Core ＋ 規則版本 ＋ 7 天有效期都過才收）；⛔ 沒有退回讀 `macro_state.json` 上限的路。\n- ⛔ 不從 `macro_state.json` 搬遷（那等於一條被禁止的退路）：首次部署時本檔不存在 ⇒ 新 UI「無法判定」，\n  直到按一次「🚀 更新今日戰情」。\n"""\n\n#: Optional 輸入的客戶語言名稱（揭露「未評估／已停用」用；與 `REQUIRED_CORE_LABELS` 同一張表的另一半）。\n#: 順序即揭露順序（客戶 2026-10-16 PQ-C6-3 線框逐字「未評估：PCR、BIAS240」）。\n#: M1B／M2 兩個鍵是同一條「M1B−M2 資金活水」腿 ⇒ 同一個名稱（呈現時去重）。\nOPTIONAL_INPUT_LABELS: Mapping[str, str] = MappingProxyType({\n    "PCR": "PCR",\n    "BIAS240_pct": "BIAS240",\n    "M1B_YoY_pct": "M1B−M2",\n    "M2_YoY_pct": "M1B−M2",\n})\n\n#: 各規則版本**依定義**停用（不計分、⛔ 不算未評估）的輸入。`risk_cap.v2` ＝ M1B-M2 腿停用（見上方版本史）。\n#: 揭露時與檔內 `disabled_inputs` 取聯集 ⇒ 就算檔內少寫，M1B／M2 也不可能被列成「未評估」。\nRULESET_DISABLED_INPUTS: Mapping[str, tuple[str, ...]] = MappingProxyType({\n    RISK_CAP_RULESET_VERSION: ("M1B_YoY_pct", "M2_YoY_pct"),\n})\n\n\nclass RiskCapDisclosure(NamedTuple):\n    """系統風險上限快照的**資料完整性揭露**（PQ-C6-3；與上限出自同一次讀檔，⛔ 渲染期不再讀檔）。\n\n    用 `NamedTuple`（凍結、可雜湊 ⇒ 可進 `allocation_service` 的快取簽章）；L0 只准 import\n    `__future__`／`types`／`typing`／`shared.*`（`tests/test_batch_z66b.py` 守），故不用 dataclasses。\n\n    Attributes:\n        snapshot_ts: 快照的 `timestamp`（台北時間字串，`macro_state_locker._TIMESTAMP_FMT`）。\n        not_evaluated: `((鍵名, 新鮮度狀態, 資料日或 None), ...)` —— 只列**Optional、未停用**的未評估項。\n            資料日**只有 `stale`（已過期）才給**：`missing` 的 `as_of_or_month` 存的是「預期資料日」，\n            不是真的資料日 ⇒ ⛔ 不得當日期顯示（§1 不造假）。\n        disabled: 停用、不計分的輸入鍵（依 `OPTIONAL_INPUTS` 順序）。\n        sahm_status: 檔內 `red_lines.sahm.status`（目前恆為 `"no_source"`）；缺 → None。\n    """\n\n    snapshot_ts: str\n    not_evaluated: tuple[tuple[str, str, str | None], ...]\n    disabled: tuple[str, ...]\n    sahm_status: str | None\n\n\ndef risk_cap_disclosure_from_snapshot(state: Mapping[str, Any]) -> RiskCapDisclosure:\n    """**已通過** `is_valid_risk_cap_snapshot` 的快照 → 揭露（純函式、不讀檔、不判有效性）。\n\n    ⛔ 停用的輸入（檔內 `disabled_inputs` ∪ `RULESET_DISABLED_INPUTS[版本]`）一律不進 `not_evaluated`。\n    """\n    _version = state.get(RISK_CAP_RULESET_VERSION_KEY)\n    _dis_raw = state.get("disabled_inputs") or ()\n    _dis_set = ({k for k in _dis_raw if isinstance(k, str)}\n                | set(RULESET_DISABLED_INPUTS.get(_version, ())))\n    disabled = tuple(k for k in OPTIONAL_INPUTS if k in _dis_set) + tuple(\n        sorted(k for k in _dis_set if k not in OPTIONAL_INPUTS))\n    _ne_raw = [k for k in (state.get("not_evaluated") or ()) if isinstance(k, str)]\n    _order = list(OPTIONAL_INPUT_LABELS) + [k for k in _ne_raw if k not in OPTIONAL_INPUT_LABELS]\n    _detail = state.get("input_detail")\n    _detail = _detail if isinstance(_detail, Mapping) else {}\n    rows: list[tuple[str, str, str | None]] = []\n    for k in _order:\n        if k not in _ne_raw or k in _dis_set:\n            continue\n        _d = _detail.get(k)\n        _d = _d if isinstance(_d, Mapping) else {}\n        _status = str(_d.get("status") or "missing")\n        _asof = _d.get("as_of_or_month") if _status == "stale" else None\n        rows.append((k, _status, str(_asof) if _asof else None))\n    _rl = state.get("red_lines")\n    _sahm = _rl.get("sahm") if isinstance(_rl, Mapping) else None\n    _sahm_status = _sahm.get("status") if isinstance(_sahm, Mapping) else None\n    return RiskCapDisclosure(\n        snapshot_ts=str(state.get("timestamp") or ""),\n        not_evaluated=tuple(rows),\n        disabled=disabled,\n        sahm_status=(str(_sahm_status) if _sahm_status is not None else None))\n',
         '            and state.get(RISK_CAP_RULESET_VERSION_KEY) == RISK_CAP_RULESET_VERSION)\n'),
    ),
    'src/services/ai_qa_service.py': (
        ('        from src.services.macro_state_locker import load_macro_state, macro_state_is_expired\n        # ~~_file = load_macro_state() or {}~~\n        # 📌 AUD-C21（客戶 2026-10-16，有意識的變更，⛔ 不是漏刪）：旗標開（新 UI 問答頁）⇒ 附加欄位／有效判斷／\n        #   `as_of` 改讀新 UI 自己的系統風險上限快照（與 `get_macro_state` 收上限的同一個檔），⛔ 不再讀\n        #   舊 UI 會整份覆寫的 `macro_state.json`；旗標關 ⇒ 逐字同修前。\n        if require_valid_risk_cap:\n            from shared.risk_cap_policy import RISK_CAP_STATE_FILE\n            _file = load_macro_state(RISK_CAP_STATE_FILE) or {}\n        else:\n            _file = load_macro_state() or {}\n        # DL-f1-s65：過期裁決（`MACRO_VERDICT_MAX_AGE_DAYS`）的附加欄位不送 AI 問答 ——\n',
         '        from src.services.macro_state_locker import load_macro_state, macro_state_is_expired\n        _file = load_macro_state() or {}\n        # DL-f1-s65：過期裁決（`MACRO_VERDICT_MAX_AGE_DAYS`）的附加欄位不送 AI 問答 ——\n'),
        ('    if _extra:\n        # AUD-C21：旗標開時這幾個欄位來自 `risk_cap_state.json` ⇒ 鍵名照實標來源（旗標關逐字同修前）。\n        _data["鎖定快照額外欄位_risk_cap_state_json" if require_valid_risk_cap\n              else "鎖定快照額外欄位_macro_state_json"] = _extra\n    return {"ok": True, "data": _data,\n',
         '    if _extra:\n        _data["鎖定快照額外欄位_macro_state_json"] = _extra\n    return {"ok": True, "data": _data,\n'),
    ),
    'src/services/allocation_service.py': (
        ('    快取簽章本來就含 `exposure_limit_pct`，新舊 UI 同一 session 交替呼叫不會互拿對方的結果。\n    📌 AUD-C21（2026-10-16，有意識的更正，⛔ 不是漏刪）：上句只在「兩邊上限值不同」時成立 —— 新 UI 的上限自本批起\n    讀自己的 `risk_cap_state.json`、舊 UI 讀 `macro_state.json`，兩者值相同時簽章會撞。現行簽章另含旗標與\n    `risk_cap_disclosure`（新 UI 的資料完整性揭露，與上限出自同一次讀檔），兩邊不再互拿。\n    """\n',
         '    快取簽章本來就含 `exposure_limit_pct`，新舊 UI 同一 session 交替呼叫不會互拿對方的結果。\n    """\n'),
        ("        _conf,\n        # AUD-C21／PQ-C6-3（2026-10-16）：揭露是決策物件的一部分 ⇒ 進簽章（只換 `not_evaluated` 也要失效）；\n        #   旗標本身也進簽章：新舊 UI 同一 session 交替呼叫、上限值剛好相同時，⛔ 不互拿對方那一份\n        #   （新 UI 那份帶揭露、舊 UI 那份不帶）。\n        bool(require_valid_risk_cap), _ms.get('risk_cap_disclosure'),\n    )\n",
         '        _conf,\n    )\n'),
    ),
    'src/services/macro_refresh_service.py': (
        ('     （新舊 UI 共用同一個引擎，兩邊一起生效）；步驟報告把它寫成「已停用、不計分」，⛔ 不算「未評估」。\n     📌 AUD-C21（客戶 2026-10-16，有意識的變更）：本步驟改為**雙寫** —— 先寫新 UI 自己的\n     `risk_cap_state.json`（`shared.risk_cap_policy.RISK_CAP_STATE_FILE`；新頁的上限只讀它），再把同一份內容\n     寫 `macro_state.json`（舊 UI 的上限來源、`get_macro_state()` 位階第 3 順位來源，照舊）。上句「寫\n     `macro_state.json`」仍屬實，只是不再是唯一的檔；逐檔結果見步驟報告與 `STEP_FILE_WRITES`。\n\n',
         '     （新舊 UI 共用同一個引擎，兩邊一起生效）；步驟報告把它寫成「已停用、不計分」，⛔ 不算「未評估」。\n\n'),
        ('from shared.macro_compute import tw_now_str\nfrom shared.risk_cap_policy import RISK_CAP_STATE_FILE\nfrom src.compute.macro.macro_session_patch import MACRO_PATCH_KEYS\n',
         'from shared.macro_compute import tw_now_str\nfrom src.compute.macro.macro_session_patch import MACRO_PATCH_KEYS\n'),
        ('    STEP_WARROOM: "紅綠燈結論（warroom_summary：燈號 / 健康分 / 位階）",\n    STEP_RISK_CAP: "系統風險上限（規則引擎 → risk_cap_state.json ＋ macro_state.json）",\n    STEP_REGISTRY: "資料登錄中心掃描",\n',
         '    STEP_WARROOM: "紅綠燈結論（warroom_summary：燈號 / 健康分 / 位階）",\n    STEP_RISK_CAP: "系統風險上限（規則引擎 → macro_state.json）",\n    STEP_REGISTRY: "資料登錄中心掃描",\n'),
        ('#: 這一步寫沒寫，看步驟報告（`STEP_RISK_CAP` 的 detail）。\n#: ~~`STEP_RISK_CAP: ("macro_state.json",),`~~\n#: 📌 AUD-C21（客戶 2026-10-16，有意識的變更，⛔ 不是漏刪）：雙寫 —— 新 UI 自己的快照檔在前（寫入順序），\n#:    `macro_state.json` 照舊（舊 UI 的上限來源＋位階第 3 順位來源，AUD-C22 不動）。\nSTEP_FILE_WRITES: dict[str, tuple[str, ...]] = {\n    STEP_RISK_CAP: (RISK_CAP_STATE_FILE, "macro_state.json"),\n}\n',
         '#: 這一步寫沒寫，看步驟報告（`STEP_RISK_CAP` 的 detail）。\nSTEP_FILE_WRITES: dict[str, tuple[str, ...]] = {\n    STEP_RISK_CAP: ("macro_state.json",),\n}\n'),
        ('            #   核心閘門保證「寫得出檔 ⇒ 紅線必可評估」⇒ 那句永遠不會出現，已刪（tests/test_batch_z66b.py 守）。\n            # ~~f"已寫入 macro_state.json：系統風險上限 "~~ —— 📌 AUD-C21（有意識的變更，⛔ 不是漏刪）：雙寫，逐檔照實報。\n            _files = tuple(getattr(_rc, "files_written", ()) or ())\n            _step(STEP_RISK_CAP, True,\n                  "；".join(f"已寫入 {_fn}" + ("（新 UI 讀的系統風險上限）" if _fn == RISK_CAP_STATE_FILE\n                                              else "（舊 UI 與市場位階備援，內容相同）")\n                           for _fn in _files)\n                  + "：系統風險上限 "\n                  f"{(_rc.engine_result or {}).get(\'exposure_limit_pct\')}%；"\n',
         '            #   核心閘門保證「寫得出檔 ⇒ 紅線必可評估」⇒ 那句永遠不會出現，已刪（tests/test_batch_z66b.py 守）。\n            _step(STEP_RISK_CAP, True,\n                  f"已寫入 macro_state.json：系統風險上限 "\n                  f"{(_rc.engine_result or {}).get(\'exposure_limit_pct\')}%；"\n'),
        ('                  f"{_rc.reason}" + _core_note + _opt_note\n                  # ~~（既有 macro_state.json 若是…~~ —— 📌 AUD-C21：新頁的上限只讀新 UI 自己的檔（有意識的更正）\n                  + f"（兩個檔都不動；既有 {RISK_CAP_STATE_FILE} 若是 {MACRO_VERDICT_MAX_AGE_DAYS} 天有效期內的有效快照"\n                  "〔Required Core 齊全、現行規則版本〕，卡①仍沿用它的上限；過期、不存在、"\n',
         '                  f"{_rc.reason}" + _core_note + _opt_note\n                  + f"（既有 macro_state.json 若是 {MACRO_VERDICT_MAX_AGE_DAYS} 天有效期內的有效快照"\n                  "〔Required Core 齊全、現行規則版本〕，卡①仍沿用它的上限；過期、不存在、"\n'),
        ('        _step(STEP_RISK_CAP, False,\n              # ~~（既有 macro_state.json 不會因此被清除）~~ —— 📌 AUD-C21：雙寫，兩個檔都照實講（有意識的更正）\n              f"{type(_e).__name__}: {_e}（既有 {RISK_CAP_STATE_FILE} 與 macro_state.json 不會因此被清除；"\n              f"若 {RISK_CAP_STATE_FILE} 已先寫入、macro_state.json 寫入失敗，{RISK_CAP_STATE_FILE} 已還原成寫入前的內容）"\n              + _rc_inputs_note)\n\n',
         '        _step(STEP_RISK_CAP, False,\n              f"{type(_e).__name__}: {_e}（既有 macro_state.json 不會因此被清除）" + _rc_inputs_note)\n\n'),
    ),
    'src/services/macro_state_locker.py': (
        ('\n    def lock_system_state_only(self, system_state: dict) -> dict:\n        """Write rule-based system_state to the state lock without calling AI.\n\n        AUD-C21（2026-10-16）：回傳**實際落檔的那一份** dict（舊 UI 呼叫端不接回傳值，行為不變）——\n        新 UI 寫端（`risk_cap_apply`）拿它經 `write_state_snapshot` 原樣再寫一份到 `macro_state.json`，\n        兩個檔逐位元組相同（同一個 `timestamp`，⛔ 不呼叫兩次各取一次時鐘）。\n\n',
         '\n    def lock_system_state_only(self, system_state: dict) -> None:\n        """Write rule-based system_state to the state lock without calling AI.\n\n'),
        ('        self._write_state_lock(final)\n        return final\n\n    def write_state_snapshot(self, state_dict: dict) -> None:\n        """把一份**已組好**的快照原子寫入 `state_file_path`（AUD-C21；與 `lock_system_state_only` 同一支寫檔）。\n\n        ⛔ 不補 `timestamp`／`analysis_summary`、不夾 `exposure_limit_pct` —— 呼叫端給的就是最終內容\n        （新 UI 雙寫：第二個檔要與第一個檔逐位元組相同）。\n        """\n        self._write_state_lock(state_dict)\n\n',
         '        self._write_state_lock(final)\n\n'),
        ('                    now=None,\n                    require_valid_risk_cap: bool = False,\n                    risk_cap_state_file_path: str | None = None) -> dict:\n    """『總經 tab 已算好的狀態』→ 全站唯一的 canonical 總經契約（① 接線 + C1 仲裁）。\n',
         '                    now=None,\n                    require_valid_risk_cap: bool = False) -> dict:\n    """『總經 tab 已算好的狀態』→ 全站唯一的 canonical 總經契約（① 接線 + C1 仲裁）。\n'),
        ('      ／`get_macro_regime(require_valid_risk_cap=True)`／`ai_qa_service.run_agent(require_valid_risk_cap=True)` 傳入。\n      📌 AUD-C21（客戶 2026-10-16，有意識的變更，⛔ 不是漏改）：上段「只取自…為 True 的檔」的那個檔，自本批起是\n      新 UI 自己的 `risk_cap_state_file_path`（預設 ＝ `state_file_path` 同目錄的\n      `shared.risk_cap_policy.RISK_CAP_STATE_FILE`；production 兩者都用預設 ⇒ `risk_cap_state.json`），\n      **不再是** `state_file_path`（`macro_state.json`，舊 UI 每次寫入都會整份覆寫它）。收件條件：讀得出來、\n      `market_regime` 非 None／「系統異常」、`macro_state_is_expired` 為 False（看**它自己的** timestamp）、\n      `is_valid_risk_cap_snapshot` 為 True、`exposure_limit_pct` 有值。⛔ 沒有退回讀 `macro_state.json`\n      上限的路（沒有新檔 ⇒ 沒有上限 ⇒「無法判定」）。位階／`is_loaded`／strict 拋錯／舊檔的 `file_error`\n      一律照舊只看 `state_file_path`（AUD-C22 不在本批）。\n      回傳 dict 多一個鍵 `risk_cap_disclosure`（`shared.risk_cap_policy.RiskCapDisclosure`；收了新檔的上限才有值，\n      否則 None）—— 資料完整性揭露與上限出自**同一次讀檔**。strict ＋ 新檔**存在卻讀不出來** ⇒ 帶\n      `file_error`（舊檔沒有 `file_error` 時才帶；舊檔的 `file_error` 逐字不變）。新檔不存在 ⇒ 沒有上限（不是錯誤）。\n      旗標關（預設、舊 UI）⇒ 本段全部不執行、回傳逐鍵同修前。\n    """\n',
         '      ／`get_macro_regime(require_valid_risk_cap=True)`／`ai_qa_service.run_agent(require_valid_risk_cap=True)` 傳入。\n    """\n'),
        ('    _exposure = _file.get("exposure_limit_pct") if _file_ok else None\n    # ~~if require_valid_risk_cap and _exposure is not None:~~\n    # ~~    # 批 Z66（Q1）：只認核心齊全＋現行規則版本的檔（fail-safe 方向：認不出來 ⇒ 沒有上限 ⇒「無法判定」）~~\n    # ~~    from shared.risk_cap_policy import is_valid_risk_cap_snapshot~~\n    # ~~    if not is_valid_risk_cap_snapshot(_file):~~\n    # ~~        _exposure = None~~\n    # 📌 AUD-C21（客戶 2026-10-16，有意識的變更，⛔ 不是漏刪）：舊寫法的有效判斷（核心齊全＋現行版本）**照搬**到\n    #   新 UI 自己的檔；被權衡掉的只是「上限讀 `macro_state.json`」這個前提 —— 舊 UI 每次寫入都把它整份覆寫。\n    _rc_disclosure = None\n    if require_valid_risk_cap:\n        _exposure, _rc_disclosure, _rc_error = _read_risk_cap_snapshot(\n            risk_cap_state_file_path if risk_cap_state_file_path is not None\n            else _sibling_risk_cap_path(state_file_path), now=now)\n        if _rc_error:\n            print(f"[macro_state_locker] ⚠️ 新 UI 系統風險上限快照讀不出來 → 本輪沒有上限：{_rc_error}")\n            if strict and not _file_error:\n                _file_error = _rc_error\n    _trend_regime = _wr.get("regime") if _wr_ok else None\n',
         '    _exposure = _file.get("exposure_limit_pct") if _file_ok else None\n    if require_valid_risk_cap and _exposure is not None:\n        # 批 Z66（Q1）：只認核心齊全＋現行規則版本的檔（fail-safe 方向：認不出來 ⇒ 沒有上限 ⇒「無法判定」）\n        from shared.risk_cap_policy import is_valid_risk_cap_snapshot\n        if not is_valid_risk_cap_snapshot(_file):\n            _exposure = None\n    _trend_regime = _wr.get("regime") if _wr_ok else None\n'),
        ('    }\n    if require_valid_risk_cap:\n        _out["risk_cap_disclosure"] = _rc_disclosure\n    if _file_error:\n',
         '    }\n    if _file_error:\n'),
        ('    return _out\n\n\ndef _sibling_risk_cap_path(state_file_path: str) -> str:\n    """`state_file_path` 同目錄的 `RISK_CAP_STATE_FILE`（預設 `macro_state.json` ⇒ `risk_cap_state.json`）。"""\n    from shared.risk_cap_policy import RISK_CAP_STATE_FILE\n    return os.path.join(os.path.dirname(state_file_path), RISK_CAP_STATE_FILE)\n\n\ndef _read_risk_cap_snapshot(path: str, *, now=None):\n    """AUD-C21：讀新 UI 的系統風險上限快照 →（上限或 None, 揭露或 None, 讀檔錯誤字串或 ""）。\n\n    只有一種情形回上限：讀得出來、`market_regime` 非 None／「系統異常」、未過期、`is_valid_risk_cap_snapshot`、\n    `exposure_limit_pct` 有值。檔不存在 ⇒ `(None, None, "")`（沒有上限，⛔ 不是錯誤）；\n    存在卻讀不出來／JSON 壞／值無法轉整數 ⇒ `(None, None, "<檔名>: <repr>")`。\n    ⛔ 不讀、不退回 `macro_state.json`。\n    """\n    from shared.risk_cap_policy import is_valid_risk_cap_snapshot, risk_cap_disclosure_from_snapshot\n    data, exc = _load_macro_state_checked(path)\n    if exc is not None:\n        if isinstance(exc, FileNotFoundError):\n            return None, None, ""\n        return None, None, f"{os.path.basename(path)}: {exc!r}"\n    if data.get("market_regime") in (None, "系統異常"):\n        return None, None, ""\n    if macro_state_is_expired(data, now=now):\n        return None, None, ""\n    if not is_valid_risk_cap_snapshot(data):\n        return None, None, ""\n    if data.get("exposure_limit_pct") is None:\n        return None, None, ""\n    return data["exposure_limit_pct"], risk_cap_disclosure_from_snapshot(data), ""\n\n',
         '    return _out\n\n'),
    ),
    'src/services/risk_cap_apply.py': (
        ('\n═══ AUD-C21：雙寫（客戶 2026-10-16 裁示；有意識的變更）═══════════════════════════\n新 UI 自己的快照檔 `shared.risk_cap_policy.RISK_CAP_STATE_FILE`（`risk_cap_state.json`）——\n舊 UI 每次寫 `macro_state.json` 都整份覆寫（兩個戳記一起洗掉），新 UI 的有效上限因此不能再住在那個檔裡。\n寫入順序：**先新檔、再 `macro_state.json`**，內容逐位元組相同（`lock_system_state_only` 回傳的那一份，\n經 `write_state_snapshot` 原樣寫第二份）。為什麼仍寫 `macro_state.json`：它是舊 UI 的上限來源、也是\n`get_macro_state()` 位階的第 3 順位來源（warroom 缺席或沒有健康分時）—— 不寫就會改變位階與舊 UI 的資料流\n（AUD-C22，客戶指示本批不動）。上方「無法計算 ⇒ 不寫檔」對**兩個檔**同樣成立（一個位元組都不動）。\n全有或全無（盡力）：新檔寫成、`macro_state.json` 寫失敗 ⇒ 新檔還原成寫入前的內容（原本不存在就刪掉），\n再把原例外往上拋（⛔ 不留下「新檔是本輪、舊檔是上一輪」的半套狀態）。逐檔結果見 `files_written`。\n\n分層（CLAUDE.md §8.2）：L3 —— 依賴 L3（`macro_engine_inputs` / `macro_state_locker`），\n',
         '\n分層（CLAUDE.md §8.2）：L3 —— 依賴 L3（`macro_engine_inputs` / `macro_state_locker`），\n'),
        ('import numbers\nimport os\nimport re\n',
         'import numbers\nimport re\n'),
        ('from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION, RISK_CAP_RULESET_VERSION_KEY\nfrom shared.risk_cap_policy import RISK_CAP_STATE_FILE\nfrom src.services.macro_state_locker import MacroStateLocker\n',
         'from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION, RISK_CAP_RULESET_VERSION_KEY\nfrom src.services.macro_state_locker import MacroStateLocker\n'),
        ('            核心齊全 ⇒ `()`）。不論有沒有寫檔都照實帶（fail-safe 時通常也是全缺）。\n        files_written: AUD-C21：這一輪**實際寫成**的檔（檔名、依寫入順序：新 UI 檔在前、`macro_state.json` 在後）。\n            `written=True` ⇔ 兩個都在；沒寫 ⇒ `()`。\n    """\n',
         '            核心齊全 ⇒ `()`）。不論有沒有寫檔都照實帶（fail-safe 時通常也是全缺）。\n    """\n'),
        ('    missing_core: tuple[str, ...] = ()\n    files_written: tuple[str, ...] = ()\n\n',
         '    missing_core: tuple[str, ...] = ()\n\n'),
        ('\ndef _restore_file(path: str, previous: bytes | None) -> None:\n    """把 `path` 還原成 `previous`（None ⇒ 原本不存在 ⇒ 刪掉）。暫存檔＋`os.replace`，⛔ 不留半截檔。"""\n    if previous is None:\n        if os.path.exists(path):\n            os.remove(path)\n        return\n    _tmp = path + ".tmp"\n    with open(_tmp, "wb") as f:\n        f.write(previous)\n    os.replace(_tmp, path)\n\n\ndef compute_and_lock_risk_cap(session: Any, *, now: datetime,\n                              state_file_path: str = "macro_state.json",\n                              risk_cap_state_file_path: str | None = None) -> RiskCapApplyResult:\n    """算一次系統風險上限；算得出來才寫（AUD-C21：先寫新 UI 的 `risk_cap_state.json`，再寫 `macro_state.json`）。\n\n',
         '\ndef compute_and_lock_risk_cap(session: Any, *, now: datetime,\n                              state_file_path: str = "macro_state.json") -> RiskCapApplyResult:\n    """算一次系統風險上限；算得出來才寫 `macro_state.json`（經 `lock_system_state_only`）。\n\n'),
        ('        state_file_path: 與 `get_macro_state()` 預設同一個相對路徑。\n        risk_cap_state_file_path: AUD-C21 新 UI 快照檔；None ⇒ `state_file_path` 同目錄的\n            `RISK_CAP_STATE_FILE`（與 `get_macro_state()` 讀端同一條預設規則）。\n\n',
         '        state_file_path: 與 `get_macro_state()` 預設同一個相對路徑。\n\n'),
        ('\n    # ~~# ⚠️ 寫檔之後不再做任何可能拋例外的事（含 print）：例外 ⇔ 這一輪沒有寫成功，呼叫端據此報告。~~\n    # ~~MacroStateLocker(state_file_path=state_file_path).lock_system_state_only(payload)~~\n    # ~~return RiskCapApplyResult(True, "", summary, payload)~~\n    # 📌 AUD-C21（客戶 2026-10-16，有意識的變更，⛔ 不是漏刪）：單寫 `macro_state.json` → 雙寫（新檔在前）。\n    #   舊寫法「寫檔後不再做可能拋例外的事」的理由仍然成立，照守：第二個檔寫完之後同樣什麼都不做。\n    _rc_path = (risk_cap_state_file_path if risk_cap_state_file_path is not None\n                else os.path.join(os.path.dirname(state_file_path), RISK_CAP_STATE_FILE))\n    try:\n        with open(_rc_path, "rb") as _f:\n            _rc_before: bytes | None = _f.read()\n    except FileNotFoundError:\n        _rc_before = None\n    _final = MacroStateLocker(state_file_path=_rc_path).lock_system_state_only(payload)   # ① 新 UI 檔\n    try:\n        MacroStateLocker(state_file_path=state_file_path).write_state_snapshot(_final)     # ② macro_state.json\n    except BaseException:\n        _restore_file(_rc_path, _rc_before)      # 盡力全有或全無；還原本身失敗會蓋過原例外往上拋（⛔ 不吞）\n        raise\n    return RiskCapApplyResult(True, "", summary, payload, files_written=(\n        os.path.basename(_rc_path), os.path.basename(state_file_path)))\n',
         '\n    # ⚠️ 寫檔之後不再做任何可能拋例外的事（含 print）：例外 ⇔ 這一輪沒有寫成功，呼叫端據此報告。\n    MacroStateLocker(state_file_path=state_file_path).lock_system_state_only(payload)\n    return RiskCapApplyResult(True, "", summary, payload)\n'),
    ),
    'src/ui/views/page_hold.py': (
        ('    has_system_risk_cap,\n)\nfrom src.ui.views.risk_cap_gate import (   # PQ-C6-3\n    RISK_CAP_COMPLETENESS_LABEL,\n    risk_cap_detail_rows,\n    risk_cap_face_text,\n)\n',
         '    has_system_risk_cap,\n)\n'),
        ('    has_risk_cap: bool = False\n    #: PQ-C6-3（客戶 2026-10-16）：L3 `AllocationDecision.risk_cap_disclosure` 原樣透傳（與上限出自同一次讀檔）。\n    #: 預設 None；只由 `load_allocation` 依 L3 實際回傳設定。⛔ 渲染期不讀檔。\n    risk_cap_disclosure: Any = None\n\n',
         '    has_risk_cap: bool = False\n\n'),
        ('        conflicts=tuple(str(_c) for _c in (getattr(_a, "conflicts", ()) or ())),\n        has_risk_cap=has_system_risk_cap(getattr(_a, "caps", ())),\n        risk_cap_disclosure=getattr(_a, "risk_cap_disclosure", None))\n\n',
         '        conflicts=tuple(str(_c) for _c in (getattr(_a, "conflicts", ()) or ())),\n        has_risk_cap=has_system_risk_cap(getattr(_a, "caps", ())))\n\n'),
        ('         "**整體資產**（市場端上限），不是核心／衛星那個組合內部的比例"),\n        # ~~「姿態油門 × macro_state 曝險上限 × …」~~ —— 📌 AUD-C21（2026-10-16，有意識的更正，⛔ 不是漏刪）：\n        #   本頁的系統風險上限自本批起讀新 UI 自己的快照檔（不再是 `macro_state.json`）⇒ 只改字、照實說。\n        ("來源", "L3 `get_allocation()`，本頁不自行再算 —— 它仲裁"\n                 "「姿態油門 × 系統風險上限 × VIX／三環天花板」"\n                 "三條輸入，**取最低**"),\n',
         '         "**整體資產**（市場端上限），不是核心／衛星那個組合內部的比例"),\n        ("來源", "L3 `get_allocation()`，本頁不自行再算 —— 它仲裁"\n                 "「姿態油門 × macro_state 曝險上限 × VIX／三環天花板」"\n                 "三條輸入，**取最低**"),\n'),
        ('    if _state == UI_LIVE:\n        # PQ-C6-3（客戶 2026-10-16 核准線框）：有系統風險上限 ⇒ 卡面多一列「資料完整性」（未評估項目名＋中性句，\n        #   ⛔ 不靠顏色），詳細各列只進「▸ 詳細」（`V2_FOLD_ONLY_FACT_KEYS`）。無上限那一態（上一段）一個字都沒加。\n        _disc = alloc.risk_cap_disclosure\n        if _disc is not None:\n            _facts.insert(0, (RISK_CAP_COMPLETENESS_LABEL, risk_cap_face_text(_disc)))\n            _facts.extend(risk_cap_detail_rows(_disc))\n        return (Card(key="hold.position_cap", label="建議持股水位（市場端）",\n',
         '    if _state == UI_LIVE:\n        return (Card(key="hold.position_cap", label="建議持股水位（市場端）",\n'),
        ('\n#: PQ-C6-3（2026-10-16）：**只進「▸ 詳細」、不上卡面**的 fact 列（卡 key → 標籤集合）。\n#: 同「🚦 今天」頁 `V2_FOLDED_FACT_KEYS` 的作法（以標籤登記）。列不在時什麼都不做（無上限那一態本來就沒有）。\nV2_FOLD_ONLY_FACT_KEYS: dict[str, frozenset[str]] = {\n    "hold.position_cap": frozenset({"快照時間", "未評估項目", "已停用（不計分）", "薩姆規則"}),\n}\n\n\ndef v2_fold_id(card: Card) -> str:\n',
         '\ndef v2_fold_id(card: Card) -> str:\n'),
        ('    _short, _full = v2_short_rows(card)\n    # PQ-C6-3：登記為「只進詳細」的列先分出來（不上卡面），原文照樣接在摺疊區最後。\n    _fold_only_keys = V2_FOLD_ONLY_FACT_KEYS.get(card.key, frozenset())\n    _fold_only = tuple((v2_plain(_k), v2_plain(_v)) for _k, _v in facts if _k in _fold_only_keys)\n    facts = tuple((_k, _v) for _k, _v in facts if _k not in _fold_only_keys)\n    _plain_facts = tuple((v2_plain(_k), v2_plain(_v)) for _k, _v in facts)\n',
         '    _short, _full = v2_short_rows(card)\n    _plain_facts = tuple((v2_plain(_k), v2_plain(_v)) for _k, _v in facts)\n'),
        ('                  if _r != _f or len(_r[1]) > v2_markup.FACT_VALUE_MAX_CHARS)\n    _folded = tuple(_full) + _long + _fold_only\n    return v2_markup.card_html(\n',
         '                  if _r != _f or len(_r[1]) > v2_markup.FACT_VALUE_MAX_CHARS)\n    _folded = tuple(_full) + _long\n    return v2_markup.card_html(\n'),
    ),
    'src/ui/views/page_today.py': (
        (')\nfrom src.ui.views.risk_cap_gate import RISK_CAP_COMPLETENESS_LABEL, risk_cap_full_text   # PQ-C6-3\nfrom src.ui.views._ui_kit import (\n',
         ')\nfrom src.ui.views._ui_kit import (\n'),
        ('        _parts.append("總經健康分有值，但契約仍回未評估")\n    # ~~`macro_state.json`~~ → `risk_cap_state.json`：📌 AUD-C21（客戶 2026-10-16，有意識的更正，⛔ 不是漏刪）——\n    #   本頁的系統風險上限自本批起只讀新 UI 自己的快照檔（`shared.risk_cap_policy.RISK_CAP_STATE_FILE`）。只改字。\n    if regime.get("exposure_limit_pct") is None:\n        _parts.append("系統風險上限（規則引擎快照 `risk_cap_state.json`）也沒有有效值")\n    else:\n        _parts.append("規則引擎快照（`risk_cap_state.json`）有系統風險上限，"\n                      "但它只是天花板、不能單獨決定建議持股")\n',
         '        _parts.append("總經健康分有值，但契約仍回未評估")\n    if regime.get("exposure_limit_pct") is None:\n        _parts.append("系統風險上限（規則引擎快照 `macro_state.json`）也沒有有效值")\n    else:\n        _parts.append("規則引擎快照（`macro_state.json`）有系統風險上限，"\n                      "但它只是天花板、不能單獨決定建議持股")\n'),
        ('            _facts.append(("硬否決天花板", alloc.cap_text))\n        # PQ-C6-3（客戶 2026-10-16 核准線框）：系統風險上限的資料完整性**上卡面**（不只藏在詳細裡）。\n        #   值＝卡面句＋「｜」＋詳細；卡面超過字數預算時契約層只截顯示、完整原文進 hover（項目清單排在最前）。\n        #   只有「有系統風險上限」才走到這裡（上方無上限分支一個字都沒加）。\n        _disc = getattr(alloc, "risk_cap_disclosure", None)\n        if _disc is not None:\n            _facts.append((RISK_CAP_COMPLETENESS_LABEL, risk_cap_full_text(_disc)))\n        if alloc.conflicts:\n',
         '            _facts.append(("硬否決天花板", alloc.cap_text))\n        if alloc.conflicts:\n'),
    ),
    'src/ui/views/risk_cap_gate.py': (
        ('    return any(getattr(c, "name", None) == SYSTEM_RISK_CAP_NAME for c in (caps or ()))\n\n\n# ══════════════════════════════════════════════════════════════════════════\n# PQ-C6-3（客戶 2026-10-16 核准線框）：系統風險上限的資料完整性揭露 —— 卡面一列＋詳細\n# ══════════════════════════════════════════════════════════════════════════\n# 兩張卡（今天頁卡① `verdict.exposure`、持股頁卡⑤ `hold.position_cap`）共用本段，⛔ 各頁不另寫一份字。\n# 揭露資料一律來自 L3 `get_allocation()` 回傳的 `AllocationDecision.risk_cap_disclosure`\n# （與上限出自同一次讀檔；本檔⛔ 不讀檔、不取數）。只在「有系統風險上限」時呈現；\n# 「建議持股：無法判定」那一態一個字都不加（客戶裁示）。\n# ⛔ 顏色不是唯一載體：完整性一律用字講（「未評估：…」）。\n\n#: 卡面那一列的標籤。\nRISK_CAP_COMPLETENESS_LABEL: str = "資料完整性"\n#: 有 Optional 未評估時，接在項目清單後面的中性句（客戶逐字；⛔ 不寫「上限可能偏寬」）。\nRISK_CAP_INCOMPLETE_SENTENCE: str = "部分訊號未納入，本次上限資訊不完整"\n#: Optional 全部可評估時（客戶逐字）。\nRISK_CAP_COMPLETE_TEXT: str = "必要與選用訊號皆已評估"\n#: 「已停用（不計分）」那一項（客戶逐字）。\nRISK_CAP_DISABLED_LABEL: str = "已停用（不計分）"\n#: 薩姆規則的固定說明（與步驟報告「薩姆規則目前無資料來源、未評估（不代表已通過）」同義、⛔ 不換說法）。\nRISK_CAP_SAHM_NO_SOURCE_TEXT: str = "目前無資料來源、未評估（不代表已通過）"\n#: 詳細裡各列的標籤。\nRISK_CAP_SNAPSHOT_TS_LABEL: str = "快照時間"\nRISK_CAP_NOT_EVALUATED_LABEL: str = "未評估項目"\nRISK_CAP_SAHM_LABEL: str = "薩姆規則"\n\n#: 新鮮度狀態 → 客戶語言（`shared.freshness_policy.FreshnessStatus` 的值；與 L3 步驟報告同一組字）。\n#: `fresh` 會出現在未評估清單裡只有一種情形：時間新鮮但值不能計分（例如非有限數）。\n_STATUS_TEXT: dict[str, str] = {\n    "missing": "未取得",\n    "stale": "已過期",\n    "undetermined": "無法判定",\n    "fresh": "資料異常、無法計分",\n}\n\n\ndef _label(key: str) -> str:\n    from shared.risk_cap_policy import OPTIONAL_INPUT_LABELS, REQUIRED_CORE_LABELS\n    return OPTIONAL_INPUT_LABELS.get(key) or REQUIRED_CORE_LABELS.get(key) or key\n\n\ndef _dedup(items) -> list[str]:\n    return list(dict.fromkeys(items))\n\n\ndef risk_cap_face_text(disclosure: Any) -> str:\n    """卡面那一列的值。有未評估項 ⇒「未評估：PCR、BIAS240；部分訊號未納入，本次上限資訊不完整」。\n\n    項目清單**排在最前**（卡面若被截斷，「未評估」與項目名仍在）；⛔ 停用的 M1B−M2 不在這裡\n    （`RiskCapDisclosure.not_evaluated` 本來就不含停用項，這裡再擋一次）。\n    """\n    _dis = set(getattr(disclosure, "disabled", ()) or ())\n    _ne = [k for k, _s, _d in (getattr(disclosure, "not_evaluated", ()) or ()) if k not in _dis]\n    if not _ne:\n        return RISK_CAP_COMPLETE_TEXT\n    return f"未評估：{\'、\'.join(_dedup(_label(k) for k in _ne))}；{RISK_CAP_INCOMPLETE_SENTENCE}"\n\n\ndef risk_cap_detail_rows(disclosure: Any) -> tuple[tuple[str, str], ...]:\n    """詳細（持股頁「▸ 詳細」／今天頁的完整文字）各列：快照時間、未評估項目、已停用、薩姆規則。\n\n    ⛔ 未取得的項目**不給日期**（檔內那一格存的是「預期資料日」，不是資料日）；已過期才帶最新資料日。\n    """\n    _rows: list[tuple[str, str]] = [\n        (RISK_CAP_SNAPSHOT_TS_LABEL, str(getattr(disclosure, "snapshot_ts", "") or "未記錄"))]\n    _dis = set(getattr(disclosure, "disabled", ()) or ())\n    _items = []\n    for k, status, as_of in (getattr(disclosure, "not_evaluated", ()) or ()):\n        if k in _dis:\n            continue\n        _txt = f"{_label(k)} {_STATUS_TEXT.get(status, \'無法評估\')}"\n        if status == "stale" and as_of:\n            _txt += f"（最新資料日 {as_of}）"\n        _items.append(_txt)\n    if _items:\n        _rows.append((RISK_CAP_NOT_EVALUATED_LABEL, "；".join(_items)))\n    if _dis:\n        _rows.append((RISK_CAP_DISABLED_LABEL, "、".join(_dedup(_label(k) for k in\n                                                          getattr(disclosure, "disabled", ())))))\n    if getattr(disclosure, "sahm_status", None) == "no_source":\n        _rows.append((RISK_CAP_SAHM_LABEL, RISK_CAP_SAHM_NO_SOURCE_TEXT))\n    return tuple(_rows)\n\n\ndef risk_cap_full_text(disclosure: Any) -> str:\n    """卡面值＋詳細接成一段（今天頁卡①那一格的完整文字：卡面截斷後掛在 hover 的就是這段）。"""\n    return "｜".join([risk_cap_face_text(disclosure)]\n                    + [f"{_k}：{_v}" for _k, _v in risk_cap_detail_rows(disclosure)])\n',
         '    return any(getattr(c, "name", None) == SYSTEM_RISK_CAP_NAME for c in (caps or ()))\n'),
    ),
}
# @@C21_PAIRS_END@@
# ── 還原組結束 ──


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def c21_revert_for(file_path, code: str) -> str:
    """舊批次還原鏈串接用：給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣）。

    由 `tests/test_batch_z66b.py::z66b_revert_for` 在它自己的 `only`／`skip` 判斷**之後**呼叫
    ⇒ z56／z66 兩條鏈各自只換自己管的檔，同一處不會被換兩次。
    """
    rel = _rel(file_path)
    for new, old in C21_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def c21_pairs_for(file_path) -> tuple:
    """給模組 `__file__`（或 repo 相對路徑），回本批該檔的還原組（無則空 tuple）。"""
    return C21_REVERT_PAIRS.get(_rel(file_path), ())


@__import__("pytest").mark.parametrize("rel", sorted(C21_REVERT_PAIRS))
def test_c21_revert_is_exact_base_source(rel):
    code = c21_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == C21_BASE_SHA[rel]


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案與舊批次測試
# ══════════════════════════════════════════════════════════════════════════
import copy  # noqa: E402
import dataclasses  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from datetime import timedelta, timezone  # noqa: E402

import pytest  # noqa: E402

from shared import risk_cap_policy as RP  # noqa: E402
from src.services import macro_refresh_service as RS  # noqa: E402
from src.services import macro_state_locker as MSL  # noqa: E402
from src.services import risk_cap_apply as RC  # noqa: E402
from src.ui.views import risk_cap_gate as G  # noqa: E402
from tests.test_batch_z64 import NOW, _build, _inputs, _li, _session_from  # noqa: E402
from tests.test_batch_z65 import (  # noqa: E402,F401
    _WR_LIVE, _WR_NO_HEALTH, _as_session, _run_refresh, _step, l1)
from tests.test_p01_macro_refresh import _mutated_module  # noqa: E402

TPE = timezone(timedelta(hours=8))
_MSL_REL = "src/services/macro_state_locker.py"
_RC_REL = "src/services/risk_cap_apply.py"
_AS_REL = "src/services/allocation_service.py"
_QA_REL = "src/services/ai_qa_service.py"
_NEW = RP.RISK_CAP_STATE_FILE
_OLD = "macro_state.json"


def _base(rel: str):
    """本批之前（3dfad58d）的那一版模組（整份原始碼換回，⛔ 不是部分突變）。"""
    cur = (REPO / rel).read_text(encoding="utf-8")
    return _mutated_module(rel, (cur, c21_revert_for(rel, cur)))


def _snapshot(*, regime="空頭", cap=30, days_ago=1.0, ok=True, version=RP.RISK_CAP_RULESET_VERSION,
              not_evaluated=(), input_detail=None, now=NOW) -> dict:
    data = {"market_regime": regime, "systemic_risk_level": "危險", "exposure_limit_pct": cap,
            "Macro_Phase": "環境正常", "analysis_summary": f"曝險上限 {cap}%（Python 規則引擎計算）",
            "timestamp": (now - timedelta(days=days_ago)).astimezone(TPE).strftime(MSL._TIMESTAMP_FMT),
            "not_evaluated": list(not_evaluated), "disabled_inputs": ["M1B_YoY_pct", "M2_YoY_pct"],
            "input_detail": dict(input_detail or {}),
            "red_lines": {"sahm": {"status": "no_source"}}}
    if ok is not None:
        data[RP.REQUIRED_CORE_OK_KEY] = ok
    if version is not None:
        data[RP.RISK_CAP_RULESET_VERSION_KEY] = version
    return data


def _put(path: Path, obj) -> bytes:
    path.write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=4),
                    encoding="utf-8")
    return path.read_bytes()


def _run(fn):
    try:
        return ("ok", fn())
    except Exception as e:  # noqa: BLE001 — 比對「同樣拋、同樣訊息」
        return ("raise", repr(e))


def _cap_of(alloc):
    return next((c.pct for c in alloc.caps if c.name == G.SYSTEM_RISK_CAP_NAME), None)


def _pcr_missing(kw):
    kw = dict(kw)
    kw["li_latest"] = _li([{"_date": "20261007", "選PCR": float("nan"), "外資大小": -1000.0},
                           {"_date": "20261013", "選PCR": float("nan"), "外資大小": -21000.0}])
    return kw


# ══════════════════════════════════════════════════════════════════════════
# 1. 覆寫回歸：舊 UI 寫入碰不到新 UI 的有效快照
# ══════════════════════════════════════════════════════════════════════════
class TestOldUiOverwrite:
    def test_old_ui_write_cannot_touch_new_snapshot(self, l1, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        kw = _inputs(vix=40.0)                     # VIX 高 ⇒ 上限低，與舊 UI 那一份可區分
        l1(kw["pmi_history"])
        res = RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW)
        assert res.written and res.files_written == (_NEW, _OLD)
        cap = res.engine_result["exposure_limit_pct"]
        rc_bytes = (tmp_path / _NEW).read_bytes()

        # 舊 UI §十一 的寫法（`section_news_ai`：calculate_system_state → MacroStateLocker() 預設路徑）
        old_numbers = _build(_inputs(vix=12.0)).macro_numbers
        old_state = MSL.calculate_system_state(old_numbers)
        assert old_state["exposure_limit_pct"] != cap
        MSL.MacroStateLocker().lock_system_state_only(old_state)
        old_file = json.loads((tmp_path / _OLD).read_text(encoding="utf-8"))
        assert not RP.is_valid_risk_cap_snapshot(old_file)          # 舊 UI 把戳記洗掉了（修前就會這樣）
        assert (tmp_path / _NEW).read_bytes() == rc_bytes            # ⭐ 新檔一個位元組都沒動

        AS = _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        new = AS.get_allocation(require_valid_risk_cap=True)
        assert _cap_of(new) == cap and new.risk_cap_disclosure is not None
        assert MSL.get_macro_state(dict(_WR_LIVE), require_valid_risk_cap=True)["exposure_limit_pct"] == cap

        # 舊 UI 的 `get_allocation()`（不帶旗標）：與修前（3dfad58d 那一版）逐欄相同
        legacy = AS.get_allocation()
        assert _cap_of(legacy) == old_state["exposure_limit_pct"] and legacy.risk_cap_disclosure is None
        base_msl = _base(_MSL_REL)
        assert base_msl.get_macro_state(dict(_WR_LIVE)) == MSL.get_macro_state(dict(_WR_LIVE))
        base_as = _base(_AS_REL)
        base_as.st = AS.st
        monkeypatch.setattr(MSL, "get_macro_state", base_msl.get_macro_state)
        AS.st.session_state.clear()
        AS.st.session_state["warroom_summary"] = dict(_WR_LIVE)
        old_dec = base_as.get_allocation()
        assert {k: v for k, v in dataclasses.asdict(legacy).items() if k != "risk_cap_disclosure"} \
            == {k: v for k, v in dataclasses.asdict(old_dec).items() if k != "risk_cap_disclosure"}


# ══════════════════════════════════════════════════════════════════════════
# 2. 位階矩陣：上限以外的每一個鍵與修前逐鍵相同
# ══════════════════════════════════════════════════════════════════════════
_WR_CASES = {"absent": None, "live": _WR_LIVE, "no_health": _WR_NO_HEALTH}
_FILE_CASES = ("old_only", "new_only", "both", "neither")
_CAP_KEYS = ("exposure_limit_pct", "risk_cap_disclosure")


class TestRegimeMatrix:
    @pytest.mark.parametrize("wr_name", list(_WR_CASES))
    @pytest.mark.parametrize("files", _FILE_CASES)
    @pytest.mark.parametrize("strict", [False, True])
    def test_non_cap_keys_identical_to_base(self, tmp_path, wr_name, files, strict):
        base = _base(_MSL_REL)
        old, new = tmp_path / _OLD, tmp_path / _NEW
        if files in ("old_only", "both"):
            _put(old, _snapshot(regime="空頭", cap=30))
        if files in ("new_only", "both"):
            _put(new, _snapshot(regime="多頭", cap=50))      # 位階故意與舊檔不同：位階⛔ 不得改讀新檔
        wr = copy.deepcopy(_WR_CASES[wr_name])
        for flag in (False, True):
            kw = dict(state_file_path=str(old), strict=strict, now=NOW, require_valid_risk_cap=flag)
            cur = _run(lambda: MSL.get_macro_state(copy.deepcopy(wr), **kw))
            ref = _run(lambda: base.get_macro_state(copy.deepcopy(wr), **kw))
            assert cur[0] == ref[0], (flag, cur, ref)
            if cur[0] == "raise":
                assert cur == ref, flag
                continue
            c, r = cur[1], ref[1]
            if not flag:
                assert c == r                                   # 旗標關：逐鍵逐值同修前
                continue
            assert {k: v for k, v in c.items() if k not in _CAP_KEYS} == \
                   {k: v for k, v in r.items() if k not in _CAP_KEYS}
            # 上限只看新檔（⛔ 無退路）
            assert c["exposure_limit_pct"] == (50 if files in ("new_only", "both") else None)
            assert (c["risk_cap_disclosure"] is None) is (files not in ("new_only", "both"))


# ══════════════════════════════════════════════════════════════════════════
# 3. 無退路：新檔不能用 ⇒ 沒有上限（舊檔再有效也不認）
# ══════════════════════════════════════════════════════════════════════════
class TestNoFallback:
    def _state(self, tmp_path, **kw):
        return MSL.get_macro_state(dict(_WR_LIVE), state_file_path=str(tmp_path / _OLD), now=NOW,
                                   require_valid_risk_cap=True, **kw)

    def test_new_missing_old_valid_v2(self, tmp_path):
        _put(tmp_path / _OLD, _snapshot(cap=30))
        s = self._state(tmp_path)
        assert s["exposure_limit_pct"] is None and s["risk_cap_disclosure"] is None
        assert "file_error" not in self._state(tmp_path, strict=True)        # 不存在 ≠ 讀壞

    @pytest.mark.parametrize("kind,snap", [
        ("expired_7_1d", dict(days_ago=7.1)),
        ("unstamped", dict(ok=None, version=None)),
        ("wrong_version", dict(version="risk_cap.v1")),
        ("core_flag_false", dict(ok=False)),
        ("fail_safe_regime", dict(regime="系統異常")),
        ("no_cap", dict(cap=None)),
    ])
    def test_new_unusable(self, tmp_path, kind, snap):
        _put(tmp_path / _OLD, _snapshot(cap=30))
        _put(tmp_path / _NEW, _snapshot(**{"cap": 50, **snap}))
        for strict in (False, True):
            s = self._state(tmp_path, strict=strict)
            assert s["exposure_limit_pct"] is None and s["risk_cap_disclosure"] is None, kind
            assert "file_error" not in s, kind          # 讀得出來、只是不能用 ⇒ 灰（無法判定），不是紅

    def test_new_valid_6_9d(self, tmp_path):
        _put(tmp_path / _NEW, _snapshot(cap=50, days_ago=6.9))
        assert self._state(tmp_path)["exposure_limit_pct"] == 50

    @pytest.mark.parametrize("content", ["{bad json", "[1, 2]", json.dumps(dict(_snapshot(), exposure_limit_pct="N/A"))])
    def test_new_corrupt(self, tmp_path, content):
        _put(tmp_path / _OLD, _snapshot(cap=30))
        _put(tmp_path / _NEW, content)
        loose = self._state(tmp_path)
        assert loose["exposure_limit_pct"] is None and "file_error" not in loose
        strict = self._state(tmp_path, strict=True)
        assert strict["exposure_limit_pct"] is None
        assert strict["file_error"].startswith(_NEW + ": ")

    def test_new_corrupt_strict_turns_hold_card_red(self, tmp_path, monkeypatch):
        from src.ui.views import page_hold as PH
        monkeypatch.chdir(tmp_path)
        _put(tmp_path / _OLD, _snapshot(cap=30, days_ago=0.0, now=_now_tpe()))
        _put(tmp_path / _NEW, "{bad json")
        _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        card, _, _ = PH.build_position_cap_card(PH.load_allocation(PH.HoldRequest(submitted=True)))
        assert card.state == PH.UI_FAILED and _NEW in card.note.why

    def test_every_new_ui_read_path_ignores_old_file(self, tmp_path, monkeypatch):
        """新 UI 的每一條上限讀取路徑：只有舊檔（有效 v2）⇒ 一律沒有上限、⛔ 不附舊檔的快照欄位。"""
        from src.services import ai_qa_service as Q
        from src.ui.views import page_hold as PH
        from src.ui.views import page_today as P
        monkeypatch.chdir(tmp_path)
        _put(tmp_path / _OLD, _snapshot(cap=30, days_ago=0.0, now=_now_tpe()))
        AS = _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        alloc, err = P._load_allocation()
        assert not err and _cap_of(alloc) is None and alloc.risk_cap_disclosure is None
        regime, rerr = P._load_regime()
        assert not rerr and regime["exposure_limit_pct"] is None
        ro = PH.load_allocation(PH.HoldRequest(submitted=True))
        assert not ro.error and not ro.has_risk_cap and ro.risk_cap_disclosure is None
        out = Q._tool_get_market_state(require_valid_risk_cap=True)
        assert out["data"]["exposure_limit_pct"] is None
        assert not any(k.startswith("鎖定快照額外欄位") for k in out["data"])
        assert out["provenance"]["as_of"] is None
        # 舊 UI（不帶旗標）照舊讀舊檔
        assert _cap_of(AS.get_allocation()) == 30
        assert Q._tool_get_market_state()["data"]["exposure_limit_pct"] == 30


def _now_tpe():
    from datetime import datetime
    return datetime.now(TPE)


# ══════════════════════════════════════════════════════════════════════════
# 4. 雙寫
# ══════════════════════════════════════════════════════════════════════════
class TestDualWrite:
    def test_refresh_writes_both_identical(self, monkeypatch, tmp_path):
        kw = _inputs(bias=None)
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                               pmi_hist=kw["pmi_history"])
        s = _step(r, RS.STEP_RISK_CAP)
        a, b = (tmp_path / _NEW).read_bytes(), (tmp_path / _OLD).read_bytes()
        assert a == b and RP.is_valid_risk_cap_snapshot(json.loads(a))
        assert s.ok and not s.skipped
        assert s.detail.index(f"已寫入 {_NEW}") < s.detail.index(f"已寫入 {_OLD}")
        assert RS.STEP_FILE_WRITES[RS.STEP_RISK_CAP] == (_NEW, _OLD)
        assert not (tmp_path / (_NEW + ".tmp")).exists() and not (tmp_path / (_OLD + ".tmp")).exists()

    def test_gate_fails_neither_written(self, monkeypatch, tmp_path):
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session={})
        assert _step(r, RS.STEP_RISK_CAP).skipped
        assert not (tmp_path / _NEW).exists() and not (tmp_path / _OLD).exists()

    def test_gate_fails_existing_both_untouched(self, monkeypatch, tmp_path):
        a = _put(tmp_path / _NEW, _snapshot(cap=50))
        b = _put(tmp_path / _OLD, _snapshot(cap=30))
        kw = _inputs(prev_month=None)          # Required Core 缺 ⇒ 閘門擋下
        r, _, _ = _run_refresh(monkeypatch, tmp_path, session=_session_from(kw),
                               pmi_hist=kw["pmi_history"])
        s = _step(r, RS.STEP_RISK_CAP)
        assert s.skipped and f"既有 {_NEW} 若是" in s.detail and "兩個檔都不動" in s.detail
        assert (tmp_path / _NEW).read_bytes() == a and (tmp_path / _OLD).read_bytes() == b

    @pytest.mark.parametrize("pre_existing", [False, True])
    def test_second_write_fails_first_restored(self, l1, tmp_path, monkeypatch, pre_existing):
        kw = _inputs()
        l1(kw["pmi_history"])
        old, new = tmp_path / _OLD, tmp_path / _NEW
        b = _put(old, _snapshot(cap=30))
        a = _put(new, _snapshot(cap=50)) if pre_existing else None

        def boom(self, state):
            raise OSError("第二個檔寫壞了")
        monkeypatch.setattr(MSL.MacroStateLocker, "write_state_snapshot", boom)
        with pytest.raises(OSError, match="第二個檔寫壞了"):
            RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW, state_file_path=str(old))
        assert old.read_bytes() == b
        assert (new.read_bytes() == a) if pre_existing else not new.exists()
        assert not (tmp_path / (_NEW + ".tmp")).exists()

    def test_new_ui_only_regime_has_rule_engine_source(self, l1, tmp_path, monkeypatch):
        """只用新 UI（從沒開過舊分頁）、warroom 缺席 ⇒ 位階仍有第 3 順位來源 —— 靠的就是雙寫的 macro_state.json。"""
        from shared import regime_arbiter as RA
        monkeypatch.chdir(tmp_path)
        kw = _inputs()
        l1(kw["pmi_history"])
        assert RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW).written
        AS = _as_session(monkeypatch, {})
        reg = AS.get_macro_regime(require_valid_risk_cap=True)
        state = json.loads((tmp_path / _OLD).read_text(encoding="utf-8"))
        assert reg["is_loaded"] and reg["source"] == RA.SOURCE_FILE_RULE_ENGINE
        assert reg["regime"] == MSL.normalize_regime(state["market_regime"])
        assert reg["exposure_limit_pct"] == state["exposure_limit_pct"]


# ══════════════════════════════════════════════════════════════════════════
# 5. 卡面揭露（PQ-C6-3）
# ══════════════════════════════════════════════════════════════════════════
_SENT = "部分訊號未納入，本次上限資訊不完整"
_CASES = {
    "pcr_missing": (lambda: _pcr_missing(_inputs()), f"未評估：PCR；{_SENT}"),
    "bias_missing": (lambda: _inputs(bias=None), f"未評估：BIAS240；{_SENT}"),
    "both_missing": (lambda: _pcr_missing(_inputs(bias=None)), f"未評估：PCR、BIAS240；{_SENT}"),
    "all_valid": (lambda: _inputs(), "必要與選用訊號皆已評估"),
}
_DATE = re.compile(r"\d{4}-\d{2}(-\d{2})?")


def _face_and_fold(html: str) -> tuple[str, str]:
    """卡面（去掉 hover `title=`）與摺疊區兩段可見文字。"""
    head, _, fold = html.partition('class="blk-fold')
    head = re.sub(r'title="[^"]*"', "", head)
    return re.sub(r"<[^>]+>", "", head), re.sub(r"<[^>]+>", "", fold)


class TestDisclosure:
    def _pages(self, l1, tmp_path, monkeypatch, kw):
        from src.ui.views import page_hold as PH
        from src.ui.views import page_today as P
        monkeypatch.chdir(tmp_path)
        l1(kw["pmi_history"])
        assert RC.compute_and_lock_risk_cap(_session_from(kw), now=NOW).written
        _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        alloc, _ = P._load_allocation()
        regime, _ = P._load_regime()
        tiles = {t.card.key: t for t in P.build_verdict_tiles(
            alloc=alloc, alloc_error="", danger=None, danger_error="",
            danger_requested=False, regime=regime, regime_error="")}
        built = PH.build_position_cap_card(PH.load_allocation(PH.HoldRequest(submitted=True)))
        return P, PH, alloc, tiles["verdict.exposure"], built

    @pytest.mark.parametrize("case", list(_CASES))
    def test_both_cards(self, l1, tmp_path, monkeypatch, case):
        make, face = _CASES[case]
        P, PH, alloc, tile, (card, facts, sig) = self._pages(l1, tmp_path, monkeypatch, make())
        d = alloc.risk_cap_disclosure
        assert d is not None and _cap_of(alloc) is not None
        assert G.risk_cap_face_text(d) == face
        assert "上限可能偏寬" not in G.risk_cap_full_text(d)
        assert all(k not in ("M1B_YoY_pct", "M2_YoY_pct") for k, _s, _a in d.not_evaluated)
        # ── 今天頁卡①：一列「資料完整性」；卡面看得到項目名，詳細在 hover ──
        tf = dict(tile.facts)
        assert tile.card.state == P.UI_LIVE and tf[G.RISK_CAP_COMPLETENESS_LABEL].startswith(face)
        t_face, _ = _face_and_fold(P.v2_card_html(tile))
        t_full = P.v2_card_html(tile)
        assert face in t_face                    # 卡面句整句可見（項目清單排最前，截斷也截不到它）
        if case != "all_valid":
            assert "未評估：" in t_face
            for lbl in ("PCR", "BIAS240"):
                assert (lbl in t_face) is (lbl in face), lbl
        assert "薩姆" not in t_face and "薩姆規則：目前無資料來源、未評估（不代表已通過）" in t_full
        assert "已停用（不計分）：M1B−M2" in t_full
        assert "M1B" not in tf[G.RISK_CAP_COMPLETENESS_LABEL].split("｜")[0]
        # ── 持股頁卡⑤：卡面一列；「▸ 詳細」列快照時間／未評估項目／已停用／薩姆 ──
        assert card.state == PH.UI_LIVE
        assert facts[0] == (G.RISK_CAP_COMPLETENESS_LABEL, face)
        h_html = PH.v2_card_html(card, facts, sig)
        h_face, h_fold = _face_and_fold(h_html)
        assert face in h_face and "▸ 詳細" in h_html and "macro_state" not in h_face
        for bad in ("薩姆", "快照時間", "已停用", "M1B"):
            assert bad not in h_face, bad
        assert "薩姆規則" in h_fold and "目前無資料來源、未評估（不代表已通過）" in h_fold
        assert "已停用（不計分）" in h_fold and "M1B−M2" in h_fold
        assert "快照時間" in h_fold and d.snapshot_ts in h_fold
        rows = dict(G.risk_cap_detail_rows(d))
        if case == "all_valid":
            assert G.RISK_CAP_NOT_EVALUATED_LABEL not in rows
        else:
            ne = rows[G.RISK_CAP_NOT_EVALUATED_LABEL]
            assert "M1B" not in ne and not _DATE.search(ne)     # 缺項（未取得）⛔ 不給日期
            assert all(f"{lbl} 未取得" in ne for lbl in face[4:face.index("；")].split("、"))
            assert ne in h_fold

    def test_bias_missing_expected_date_never_shown(self, l1, tmp_path, monkeypatch):
        """BIAS240 缺時檔內 `input_asof`／`as_of_or_month` 存的是**預期**資料日 ⇒ 卡面與詳細都⛔ 不出現。"""
        kw = _inputs(bias=None)
        P, PH, alloc, tile, (card, facts, sig) = self._pages(l1, tmp_path, monkeypatch, kw)
        state = json.loads((tmp_path / _NEW).read_text(encoding="utf-8"))
        expected = state["input_detail"]["BIAS240_pct"]["as_of_or_month"]
        assert state["input_detail"]["BIAS240_pct"]["status"] == "missing" and expected
        assert ("BIAS240_pct", "missing", None) in alloc.risk_cap_disclosure.not_evaluated
        full = G.risk_cap_full_text(alloc.risk_cap_disclosure)
        assert "BIAS240 未取得（" not in full and expected not in full
        assert expected not in PH.v2_card_html(card, facts, sig) and expected not in P.v2_card_html(tile)

    def test_stale_item_shows_real_data_date(self):
        d = RP.risk_cap_disclosure_from_snapshot(_snapshot(
            not_evaluated=["BIAS240_pct"],
            input_detail={"BIAS240_pct": {"status": "stale", "as_of_or_month": "2026-09-01"}}))
        assert dict(G.risk_cap_detail_rows(d))[G.RISK_CAP_NOT_EVALUATED_LABEL] == \
            "BIAS240 已過期（最新資料日 2026-09-01）"

    def test_m1b_never_listed_even_if_file_says_so(self):
        snap = _snapshot(not_evaluated=["M1B_YoY_pct", "M2_YoY_pct", "PCR"])
        snap["disabled_inputs"] = []                       # 就算檔內少寫停用清單：v2 依定義停用
        d = RP.risk_cap_disclosure_from_snapshot(snap)
        assert [k for k, _s, _a in d.not_evaluated] == ["PCR"]
        assert d.disabled == ("M1B_YoY_pct", "M2_YoY_pct")
        assert G.risk_cap_face_text(d) == f"未評估：PCR；{_SENT}"
        assert dict(G.risk_cap_detail_rows(d))[G.RISK_CAP_DISABLED_LABEL] == "M1B−M2"

    def test_no_disclosure_without_cap(self, tmp_path, monkeypatch):
        from src.ui.views import page_hold as PH
        from src.ui.views import page_today as P
        monkeypatch.chdir(tmp_path)
        _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        alloc, _ = P._load_allocation()
        assert alloc.is_loaded and _cap_of(alloc) is None and alloc.risk_cap_disclosure is None
        tile = {t.card.key: t for t in P.build_verdict_tiles(
            alloc=alloc, alloc_error="", danger=None, danger_error="", danger_requested=False,
            regime=P._load_regime()[0], regime_error="")}["verdict.exposure"]
        assert tile.card.state == P.UI_EMPTY and tile.card.note.now == G.RISK_CAP_UNAVAILABLE_NOW
        assert G.RISK_CAP_COMPLETENESS_LABEL not in dict(tile.facts)
        card, facts, _ = PH.build_position_cap_card(PH.load_allocation(PH.HoldRequest(submitted=True)))
        assert card.state == PH.UI_EMPTY and G.RISK_CAP_COMPLETENESS_LABEL not in dict(facts)
        html = PH.v2_card_html(card, facts, "")
        assert "資料完整性" not in html and "未評估：" not in html

    def test_cache_returns_fresh_disclosure(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        AS = _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        _put(tmp_path / _NEW, _snapshot(cap=40, days_ago=0.0, now=_now_tpe(), not_evaluated=["PCR"]))
        a = AS.get_allocation(require_valid_risk_cap=True)
        _put(tmp_path / _NEW, _snapshot(cap=40, days_ago=0.0, now=_now_tpe(), not_evaluated=["BIAS240_pct"]))
        b = AS.get_allocation(require_valid_risk_cap=True)
        assert _cap_of(a) == _cap_of(b) == 40
        assert [k for k, *_ in a.risk_cap_disclosure.not_evaluated] == ["PCR"]
        assert [k for k, *_ in b.risk_cap_disclosure.not_evaluated] == ["BIAS240_pct"]
        # 新舊 UI 交替、上限值剛好相同：⛔ 不互拿對方那一份
        _put(tmp_path / _OLD, _snapshot(cap=40, days_ago=0.0, now=_now_tpe()))
        assert AS.get_allocation().risk_cap_disclosure is None
        assert AS.get_allocation(require_valid_risk_cap=True).risk_cap_disclosure is not None


# ══════════════════════════════════════════════════════════════════════════
# 6. 突變自驗（恰一次字面替換 → 守衛必須轉紅）
# ══════════════════════════════════════════════════════════════════════════
class TestMutations:
    def test_reader_falls_back_to_old_file(self, tmp_path):
        mod = _mutated_module(_MSL_REL, ("            else _sibling_risk_cap_path(state_file_path), now=now)",
                                         "            else state_file_path, now=now)"))
        _put(tmp_path / _OLD, _snapshot(cap=30))
        kw = dict(state_file_path=str(tmp_path / _OLD), now=NOW, require_valid_risk_cap=True)
        assert MSL.get_macro_state(dict(_WR_LIVE), **kw)["exposure_limit_pct"] is None
        assert mod.get_macro_state(dict(_WR_LIVE), **kw)["exposure_limit_pct"] == 30   # 突變體退回舊檔 ⇒ 原版守衛必紅

    def test_dual_write_dropped(self, l1, tmp_path, monkeypatch):
        mod = _mutated_module(_RC_REL, (
            "        MacroStateLocker(state_file_path=state_file_path).write_state_snapshot(_final)",
            "        pass"))
        monkeypatch.chdir(tmp_path)
        kw = _inputs()
        l1(kw["pmi_history"])
        assert mod.compute_and_lock_risk_cap(_session_from(kw), now=NOW).written
        assert (tmp_path / _NEW).exists() and not (tmp_path / _OLD).exists()
        AS = _as_session(monkeypatch, {})
        assert not AS.get_macro_regime(require_valid_risk_cap=True)["is_loaded"]   # 原版守衛（位階有第 3 來源）必紅

    def test_validity_filter_removed(self, tmp_path):
        mod = _mutated_module(_MSL_REL, ("    if not is_valid_risk_cap_snapshot(data):\n",
                                         "    if False:\n"))
        _put(tmp_path / _NEW, _snapshot(cap=50, version="risk_cap.v1"))
        kw = dict(state_file_path=str(tmp_path / _OLD), now=NOW, require_valid_risk_cap=True)
        assert MSL.get_macro_state(None, **kw)["exposure_limit_pct"] is None
        assert mod.get_macro_state(None, **kw)["exposure_limit_pct"] == 50

    def test_disclosure_lists_m1b(self):
        snap = _snapshot(not_evaluated=["M1B_YoY_pct", "PCR"])
        mod = _mutated_module("shared/risk_cap_policy.py", (
            "        if k not in _ne_raw or k in _dis_set:\n", "        if k not in _ne_raw:\n"))
        assert "M1B_YoY_pct" not in [k for k, *_ in RP.risk_cap_disclosure_from_snapshot(snap).not_evaluated]
        assert "M1B_YoY_pct" in [k for k, *_ in mod.risk_cap_disclosure_from_snapshot(snap).not_evaluated]
        gmod = _mutated_module("src/ui/views/risk_cap_gate.py", (
            "    _ne = [k for k, _s, _d in (getattr(disclosure, \"not_evaluated\", ()) or ()) if k not in _dis]",
            "    _ne = [k for k, _s, _d in (getattr(disclosure, \"not_evaluated\", ()) or ())]"))
        leaky = RP.RiskCapDisclosure("t", (("M1B_YoY_pct", "missing", None),), ("M1B_YoY_pct", "M2_YoY_pct"), None)
        assert "M1B" not in G.risk_cap_face_text(leaky)
        assert "M1B" in gmod.risk_cap_face_text(leaky)

    def test_cache_signature_without_disclosure(self, tmp_path, monkeypatch):
        mod = _mutated_module(_AS_REL, (
            "        bool(require_valid_risk_cap), _ms.get('risk_cap_disclosure'),\n", ""))
        monkeypatch.chdir(tmp_path)
        AS = _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        mod.st = AS.st
        _put(tmp_path / _NEW, _snapshot(cap=40, days_ago=0.0, now=_now_tpe(), not_evaluated=["PCR"]))
        mod.get_allocation(require_valid_risk_cap=True)
        _put(tmp_path / _NEW, _snapshot(cap=40, days_ago=0.0, now=_now_tpe(), not_evaluated=["BIAS240_pct"]))
        stale = mod.get_allocation(require_valid_risk_cap=True)
        assert [k for k, *_ in stale.risk_cap_disclosure.not_evaluated] == ["PCR"]   # 突變體回舊揭露 ⇒ 原版守衛必紅


# ══════════════════════════════════════════════════════════════════════════
# 7. 其餘讀寫面
# ══════════════════════════════════════════════════════════════════════════
class TestOtherPaths:
    def test_ai_qa_flag_off_identical_to_base(self, tmp_path, monkeypatch):
        from src.services import ai_qa_service as Q
        monkeypatch.chdir(tmp_path)
        _put(tmp_path / _OLD, _snapshot(cap=30, days_ago=0.0, now=_now_tpe()))
        _put(tmp_path / _NEW, _snapshot(cap=50, days_ago=0.0, now=_now_tpe()))
        _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        base = _base(_QA_REL)
        assert Q._tool_get_market_state() == base._tool_get_market_state()

    def test_ai_qa_flag_on_reads_new_file(self, tmp_path, monkeypatch):
        from src.services import ai_qa_service as Q
        monkeypatch.chdir(tmp_path)
        _put(tmp_path / _OLD, dict(_snapshot(cap=30, days_ago=0.0, now=_now_tpe()), Macro_Phase="舊檔"))
        new = dict(_snapshot(cap=50, days_ago=0.0, now=_now_tpe()), Macro_Phase="新檔")
        _put(tmp_path / _NEW, new)
        _as_session(monkeypatch, {"warroom_summary": dict(_WR_LIVE)})
        out = Q._tool_get_market_state(require_valid_risk_cap=True)
        assert out["data"]["exposure_limit_pct"] == 50
        assert out["data"]["鎖定快照額外欄位_risk_cap_state_json"]["Macro_Phase"] == "新檔"
        assert "鎖定快照額外欄位_macro_state_json" not in out["data"]
        assert out["provenance"]["as_of"] == new["timestamp"]

    def test_gitignore_and_constant(self):
        gi = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert RP.RISK_CAP_STATE_FILE == "risk_cap_state.json"
        assert "risk_cap_state.json" in gi and "risk_cap_state.json.tmp" in gi
        assert _sibling_default() == "risk_cap_state.json"

    def test_page_today_cap_wording_names_new_file(self):
        from src.ui.views import page_today as P
        txt = P._alloc_unloaded_why({"health": None, "exposure_limit_pct": None})
        assert "`risk_cap_state.json`" in txt and "macro_state.json" not in txt
        txt2 = P._alloc_unloaded_why({"health": 50.0, "exposure_limit_pct": 30})
        assert "`risk_cap_state.json`" in txt2 and "macro_state.json" not in txt2


def _sibling_default() -> str:
    return MSL._sibling_risk_cap_path("macro_state.json")
