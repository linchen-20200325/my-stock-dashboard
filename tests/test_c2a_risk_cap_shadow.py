"""C2a-2（DEC-080，客戶 2026-10-24）—— Risk Cap 寫檔分支附加 `input_provenance_shadow` 觀測欄（⛔ 零投資輸出變更）。

只改 `src/services/risk_cap_apply.py`：三道閘門（fail-safe／非有限上限／Required Core）之後的寫檔分支，
把 L2 `infer_input_provenance` 的逐項紀錄附進兩個快照檔（`risk_cap_state.json`＋`macro_state.json`）。

守：
1. 還原鏈：`C2A_REVERT_PAIRS`（C2a-2 後逐字 → 前逐字，`difflib` 對 `git show 0a78f308:<檔>` 最小唯一上下文產生）
   還原體逐位＝基底 sha；只套一次；鏈頭接在 `c1_revert_for` 之前（`tests/test_c1_observability.py`），
   舊批次鏈（dec074／vn1store／c21／z66b…）的基底 sha 守衛因此不轉紅。
2. 零輸出 before／after 情境網格：同一組輸入、同一個時鐘，現行版與還原體（C2a-2 前）逐輪比對 ——
   `RiskCapApplyResult` 的 written／reason／missing_core／files_written／bundle_summary 相同；
   engine_result 去掉觀測欄後逐鍵逐值（含鍵順序）相同；兩個檔去掉觀測欄後**逐位元組**相同；
   沒寫檔的輪次兩邊都不寫檔、現行版也不記觀測欄；stdout 相同；讀端 `get_macro_state` 輸出相同。
3. 觀測欄內容：鍵集合＝L0 `INPUT_POLICY`、紀錄＝直接呼叫 L2 的結果、可 JSON 化、兩檔相同。
4. 失敗注入（每一種都：照樣寫兩個檔、核心內容與還原體逐位相同、觀測欄帶可追溯錯誤標記、無 `.tmp` 孤兒）：
   (a) 分類拋例外 (b) import 失敗 (c) lone surrogate 來源字串 (d) NaN／inf (e) 超長字串（截長、不失敗）
   (f) PMI 歷史重讀拋例外 (g) 觀測欄 log 時 stdout broken pipe／非 UTF-8／stdout＋stderr 全壞；另含非 JSON 型別。
5. 唯讀：session／bundle／引擎輸出不被改。
6. 讀者守衛：產品碼除 `risk_cap_apply.py` 外零讀者；`risk_cap_apply.py` 不含 `_pcr_src`／`PCR_SOURCE_COLUMN`／
   `is_proxy`；`RISK_CAP_RULESET_VERSION`／`ENGINE_SOURCE`／`PRODUCTION_WRITE_APPROVED` 不變。
7. 突變自驗：拿掉 utf-8 自驗 ⇒ (c) 整輪失敗並留 `.tmp`；拿掉例外攔截 ⇒ (a) 整輪失敗。
L1（休市表、PMI parquet）一律 mock；不連網。
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原組（先於任何專案 import 定義 —— `c1_revert_for` 會回頭 import 本表）
# ══════════════════════════════════════════════════════════════════════════
_RC_REL = "src/services/risk_cap_apply.py"
#: 基底 `0a78f308`（main，C2a-2 開工前）原始檔 sha256（`git show 0a78f308:<檔> | sha256sum` 實算；寫死以免依賴 git）。
C2A_BASE_SHA = {_RC_REL: "e4e6c0f3cf553418fefd124c1c5732b66ebaeaf4350759bc4745c8e4db8a59b9"}

# >>> C2A_REVERT_PAIRS（difflib 對基底逐 hunk、最小唯一上下文產生；改 risk_cap_apply.py 後須整組重產）
C2A_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'src/services/risk_cap_apply.py': (('\n'
                                     '═══ C2a-2：資料身分 × 新鮮度觀測欄（客戶裁示 DEC-080；⛔ 純觀測、零投資輸出變更）═══════════\n'
                                     '寫檔分支（三道閘門 fail-safe／非有限上限／Required Core 都過之後）在快照多附一個鍵\n'
                                     '`input_provenance_shadow`（`INPUT_PROVENANCE_SHADOW_KEY`），兩個檔同一份內容：\n'
                                     '  成功 ⇒ `{"shadow_policy_version": <L0 SHADOW_POLICY_VERSION>, '
                                     '"inputs": {引擎輸入名: 紀錄}}`\n'
                                     '         （紀錄＝L2 '
                                     '`src/compute/macro/input_provenance.infer_input_provenance` '
                                     '的逐項輸出，字串截長）；\n'
                                     '  失敗 ⇒ `{"_error": <例外型別名>, "_stage": <階段>}`（＋log 也寫不出去時 '
                                     '`_log_error`）。\n'
                                     '- 沒寫檔的輪次（三道閘門任一擋下）**什麼都不記**（觀測欄只活在檔案裡，不另寫任何地方）。\n'
                                     '- ⛔ 不改：上限值、計分資格、Required Core、門檻／公式／權重、位階／燈號、哪些輪次寫檔、reason 字串；\n'
                                     '  觀測欄**任何**失敗（import、PMI 歷史重讀、分類、非 JSON 型別、NaN／inf、lone surrogate '
                                     '編碼…）\n'
                                     '  只把觀測欄換成錯誤標記＋印一行安全 log，⛔ 不讓原本會寫成功的一輪變失敗（也不留 `.tmp` 孤兒）。\n'
                                     '- 自驗與 `_write_state_lock` 的實際編碼逐條對齊：`json.dumps(..., '
                                     'ensure_ascii=False, allow_nan=False)`\n'
                                     '  再 `.encode("utf-8")`（落檔是 `json.dump(ensure_ascii=False)` 寫進 utf-8 '
                                     '文字檔 ⇒ lone surrogate\n'
                                     '  只在寫檔當下才炸；舊的 `json.dumps` 前檢查不 encode、抓不到）。\n'
                                     '- PMI 歷史：bundle 沒保存它 ⇒ 以引擎同一支 L1 '
                                     '`macro_cache_reader.load_tw_pmi_history()` **再讀一次本地檔**\n'
                                     '  （⛔ 不新增來源、不連網）。⚠️ 已知限制（據實揭露）：兩次讀之間 cron 若換掉 parquet，觀測欄看到的可能\n'
                                     '  與引擎用的不是同一版 —— 只影響觀測欄的 PMI 前月紀錄，⛔ 不影響上限。\n'
                                     '- 讀者：產品碼零讀者（`tests/test_c2a_risk_cap_shadow.py` 守）；不上 '
                                     'UI（`RC-VISIBILITY`）。\n'
                                     '\n'
                                     '分層（CLAUDE.md §8.2）：L3 —— 依賴 L3（`macro_engine_inputs` / '
                                     '`macro_state_locker`），\n',
                                     '\n'
                                     '分層（CLAUDE.md §8.2）：L3 —— 依賴 L3（`macro_engine_inputs` / '
                                     '`macro_state_locker`），\n'),
                                    ('零 L4 / L5 import、不 import streamlit、**不寫 session**（session '
                                     '由呼叫端傳入，唯讀）。\n'
                                     'C2a-2 觀測欄另在函式內延遲 import L0 '
                                     '`shared.input_provenance_policy`／`shared.na_drop_log`、\n'
                                     'L2 `src.compute.macro.input_provenance`、L1 '
                                     '`src.data.macro.macro_cache_reader`（皆為下行依賴）。\n'
                                     '"""\n',
                                     '零 L4 / L5 import、不 import streamlit、**不寫 session**（session '
                                     '由呼叫端傳入，唯讀）。\n'
                                     '"""\n'),
                                    ('\n'
                                     '#: C2a-2（DEC-080）：寫檔分支附加的觀測欄鍵名。⛔ 純觀測：產品碼零讀者、不上 UI。\n'
                                     'INPUT_PROVENANCE_SHADOW_KEY: str = "input_provenance_shadow"\n'
                                     '\n'
                                     '#: 附帶欄位（引擎原有鍵以外、本檔加進檔案的鍵）。⛔ 不得與引擎輸出重名。\n',
                                     '\n#: 附帶欄位（引擎原有鍵以外、本檔加進檔案的鍵）。⛔ 不得與引擎輸出重名。\n'),
                                    ('#: 附帶欄位（引擎原有鍵以外、本檔加進檔案的鍵）。⛔ 不得與引擎輸出重名。\n'
                                     '#: C2a-2：加入觀測欄鍵（同一道重名守衛；引擎從不輸出此鍵 ⇒ 不改變任何一輪的結果）。\n'
                                     'ATTACHED_KEYS: tuple[str, ...] = ("engine_source", "input_detail", '
                                     '"m1b_m2_data_month",\n',
                                     '#: 附帶欄位（引擎原有鍵以外、本檔加進檔案的鍵）。⛔ 不得與引擎輸出重名。\n'
                                     'ATTACHED_KEYS: tuple[str, ...] = ("engine_source", "input_detail", '
                                     '"m1b_m2_data_month",\n'),
                                    ('ATTACHED_KEYS: tuple[str, ...] = ("engine_source", "input_detail", '
                                     '"m1b_m2_data_month",\n'
                                     '                                  RISK_CAP_RULESET_VERSION_KEY, '
                                     'REQUIRED_CORE_OK_KEY,\n'
                                     '                                  INPUT_PROVENANCE_SHADOW_KEY)\n'
                                     '\n'
                                     '#: C2a-2：觀測欄內每個字串（含 dict 鍵）的長度上限（字元數）。\n'
                                     '#: **技術常數，不是投資參數**：只防上游異常字串把快照檔撐大／log 洪水；不影響任何計分、門檻、上限、\n'
                                     '#: 寫不寫檔。測試情境網格實測正常紀錄最長字串 185 字（2026-10-24），512 只截異常值；截斷時附註原長度（⛔ '
                                     '不靜默截）。\n'
                                     'SHADOW_STR_MAX_LEN: int = 512\n'
                                     '_SHADOW_TRUNCATED_NOTE: str = "…[truncated:{n}]"\n'
                                     '\n'
                                     '#: C2a-2：觀測欄讀的 session 鍵（＝ '
                                     '`macro_engine_inputs.load_engine_inputs_from_session` 讀的同 5 個；\n'
                                     '#: 也是 L2 `infer_input_provenance` 的同名參數）。只讀。\n'
                                     '_SHADOW_SESSION_KEYS: tuple[str, ...] = ("macro_info", "bias_info", '
                                     '"m1b_m2_info", "li_latest", "mkt_info")\n'
                                     '\n',
                                     'ATTACHED_KEYS: tuple[str, ...] = ("engine_source", "input_detail", '
                                     '"m1b_m2_data_month",\n'
                                     '                                  RISK_CAP_RULESET_VERSION_KEY, '
                                     'REQUIRED_CORE_OK_KEY)\n'
                                     '\n'),
                                    ('            （不含 `analysis_summary` / `timestamp`，那兩個由 '
                                     '`lock_system_state_only` 補）。\n'
                                     '            C2a-2：寫檔時多帶 `input_provenance_shadow`（純觀測；呼叫端 '
                                     '`refresh_macro_now` 只讀\n'
                                     '            `exposure_limit_pct`，⛔ 不得讀觀測欄）。\n'
                                     '        missing_core: 批 Z66（Q1）：無法評估的 Required Core 鍵名（依 '
                                     '`REQUIRED_CORE_INPUTS` 順序；\n',
                                     '            （不含 `analysis_summary` / `timestamp`，那兩個由 '
                                     '`lock_system_state_only` 補）。\n'
                                     '        missing_core: 批 Z66（Q1）：無法評估的 Required Core 鍵名（依 '
                                     '`REQUIRED_CORE_INPUTS` 順序；\n'),
                                    ('\n'
                                     '# '
                                     '══════════════════════════════════════════════════════════════════════\n'
                                     '# C2a-2：資料身分 × 新鮮度觀測欄（純觀測；⛔ 任何失敗都不得改變本輪寫不寫檔）\n'
                                     '# '
                                     '══════════════════════════════════════════════════════════════════════\n'
                                     '\n'
                                     '\n'
                                     'def _ascii_name(text: str) -> str:\n'
                                     '    """錯誤標記用：轉成 ASCII 跳脫版並截長（例外型別名理論上也可含 lone surrogate；⛔ '
                                     '不讓標記本身寫不出去）。"""\n'
                                     '    return str(text).encode("ascii", '
                                     '"backslashreplace").decode("ascii")[:SHADOW_STR_MAX_LEN]\n'
                                     '\n'
                                     '\n'
                                     'def _shadow_copy(v: Any) -> Any:\n'
                                     '    """觀測欄 → 新的純 JSON 結構（深拷貝，不與上游共用可變物件）；字串截長。\n'
                                     '\n'
                                     '    只收 None／bool／int／float／str 與 str 鍵的 dict、list／tuple；其他型別（含 numpy '
                                     '純量）→ TypeError\n'
                                     '    （⛔ 不猜怎麼轉，交給呼叫端換成錯誤標記）。NaN／±inf 不在這裡擋，交給之後的 `allow_nan=False` 自驗。\n'
                                     '    """\n'
                                     '    if v is None or isinstance(v, (bool, int, float)):\n'
                                     '        return v\n'
                                     '    if isinstance(v, str):\n'
                                     '        return v if len(v) <= SHADOW_STR_MAX_LEN else (\n'
                                     '            v[:SHADOW_STR_MAX_LEN] + '
                                     '_SHADOW_TRUNCATED_NOTE.format(n=len(v)))\n'
                                     '    if isinstance(v, dict):\n'
                                     '        out: dict[str, Any] = {}\n'
                                     '        for k, x in v.items():\n'
                                     '            if not isinstance(k, str):\n'
                                     '                raise TypeError(f"觀測欄 dict 鍵不是字串：{type(k).__name__}")\n'
                                     '            out[_shadow_copy(k)] = _shadow_copy(x)\n'
                                     '        return out\n'
                                     '    if isinstance(v, (list, tuple)):\n'
                                     '        return [_shadow_copy(x) for x in v]\n'
                                     '    raise TypeError(f"觀測欄含非 JSON 型別：{type(v).__name__}")\n'
                                     '\n'
                                     '\n'
                                     'def _shadow_error(stage: str, exc: BaseException) -> dict:\n'
                                     '    """失敗標記：只記例外型別名與階段（⛔ 不放例外訊息 —— 可能夾帶上游原文／編碼炸彈）。"""\n'
                                     '    return {"_error": _ascii_name(type(exc).__name__), "_stage": '
                                     'stage}\n'
                                     '\n'
                                     '\n'
                                     'def _log_shadow_failure(marker: dict) -> None:\n'
                                     '    """印一行觀測欄失敗 log；stdout／stderr 寫不出去 ⇒ 改把 log 失敗記進標記 `_log_error`（⛔ '
                                     '不往外拋）。\n'
                                     '\n'
                                     '    沿用 L0 `shared.na_drop_log._safe_print`（stdout 非 UTF-8 ⇒ ASCII '
                                     '跳脫版；None／已關閉／broken pipe\n'
                                     '    ⇒ 改寫 `sys.__stderr__`；行為逐條見該檔 docstring），⛔ 不在這裡另寫一套。它唯二會往外拋的情形\n'
                                     '    （stderr 拋 OSError／ValueError 以外的例外、或它自己 import 失敗）由下方 except 收成 '
                                     '`_log_error`\n'
                                     '    —— 有留痕（寫進檔案的觀測欄），不是吞例外。\n'
                                     '    """\n'
                                     '    msg = (f"[risk_cap_apply] ⚠️ {INPUT_PROVENANCE_SHADOW_KEY} 觀測失敗"\n'
                                     '           f"（階段 {marker.get(\'_stage\')}：{marker.get(\'_error\')}）→ '
                                     '觀測欄只記錯誤標記；"\n'
                                     '           "本輪是否寫檔不受觀測欄影響")\n'
                                     '    try:\n'
                                     '        from shared.na_drop_log import _safe_print\n'
                                     '        _safe_print(msg)\n'
                                     '    except Exception as _e:  # noqa: BLE001 — log 是純觀測；失敗改留痕在標記裡（見上）\n'
                                     '        marker["_log_error"] = _ascii_name(type(_e).__name__)\n'
                                     '\n'
                                     '\n'
                                     'def _input_provenance_shadow(session: Any, bundle: EngineInputBundle) '
                                     '-> dict:\n'
                                     '    """C2a-2 觀測欄：本輪引擎輸入逐項的 provenance／freshness／五欄資格（⛔ 不 raise '
                                     '`Exception`）。\n'
                                     '\n'
                                     '    唯讀：`session`、`bundle`（及引擎輸出）一個都不改；L2 分類是純函式，回傳值另做深拷貝。\n'
                                     '    `scored_keys` 依 L2 docstring 公式：`macro_numbers` 值非 None '
                                     '的鍵，扣掉停用（M1B／M2）。\n'
                                     '    ⚠️ 只攔 `Exception`：KeyboardInterrupt／SystemExit 照常往外（與本檔其餘路徑相同，⛔ '
                                     '不攔中斷）。\n'
                                     '    """\n'
                                     '    stage = "import"\n'
                                     '    try:\n'
                                     '        # 延遲 import（稽核第 3 點）：新模組 import 失敗只影響觀測欄，⛔ 不讓整個 risk_cap_apply '
                                     '載不起來。\n'
                                     '        from shared.input_provenance_policy import '
                                     'SHADOW_POLICY_VERSION\n'
                                     '        from src.compute.macro.input_provenance import '
                                     'infer_input_provenance\n'
                                     '        from src.data.macro import macro_cache_reader as _mcr_shadow\n'
                                     '\n'
                                     '        stage = "pmi_history"\n'
                                     '        # 與引擎（`load_engine_inputs_from_session`）同一支 '
                                     'L1、同一個本地檔再讀一次（bundle 沒保存歷史表）。\n'
                                     '        # ⚠️ 已知限制：兩次讀之間 cron 若換掉 parquet，這裡看到的可能是另一版 —— 只影響觀測欄（據實揭露）。\n'
                                     '        pmi_history = _mcr_shadow.load_tw_pmi_history()\n'
                                     '\n'
                                     '        stage = "session"\n'
                                     '        _get = session.get\n'
                                     '        raw = {k: _get(k) for k in _SHADOW_SESSION_KEYS}\n'
                                     '\n'
                                     '        stage = "infer"\n'
                                     '        scored = ({k for k, v in bundle.macro_numbers.items() if v is '
                                     'not None}\n'
                                     '                  - set(bundle.disabled_inputs))\n'
                                     '        records = infer_input_provenance(**raw, '
                                     'pmi_history=pmi_history,\n'
                                     '                                         assessed=bundle.assessed, '
                                     'scored_keys=scored)\n'
                                     '\n'
                                     '        stage = "sanitize"\n'
                                     '        shadow = _shadow_copy({"shadow_policy_version": '
                                     'SHADOW_POLICY_VERSION, "inputs": records})\n'
                                     '\n'
                                     '        stage = "validate"\n'
                                     '        # 稽核第 1 點（必修）：與 `_write_state_lock` 落檔同一種編碼路徑自驗 —— 只過 '
                                     '`json.dumps` 不夠，\n'
                                     '        #   lone surrogate（例 "\\ud800"）要到 utf-8 encode '
                                     '才炸；炸在寫檔當下會讓整輪失敗並留 `.tmp` 孤兒。\n'
                                     '        json.dumps(shadow, ensure_ascii=False, '
                                     'allow_nan=False).encode("utf-8")\n'
                                     '        return shadow\n'
                                     '    except Exception as exc:  # noqa: BLE001 — 觀測欄失敗：換成錯誤標記＋安全 '
                                     'log（有留痕，不是吞例外）\n'
                                     '        marker = _shadow_error(stage, exc)\n'
                                     '        _log_shadow_failure(marker)\n'
                                     '        return marker\n'
                                     '\n'
                                     '\n'
                                     'def compute_and_lock_risk_cap(session: Any, *, now: datetime,\n',
                                     '\ndef compute_and_lock_risk_cap(session: Any, *, now: datetime,\n'),
                                    ('    payload[REQUIRED_CORE_OK_KEY] = True     # 批 Z66（Q1）：走到這裡 ⇔ '
                                     'Required Core 全部可評估\n'
                                     '    # C2a-2（DEC-080）：三道閘門之後才建觀測欄（沒寫檔的輪次不記錄）；排在下一行前檢查之前 ⇒ 前檢查照舊\n'
                                     '    #   涵蓋整份 payload。觀測欄自己已做完 utf-8 自驗、失敗只回錯誤標記 ⇒ ⛔ 不會讓本來寫得成的一輪變失敗。\n'
                                     '    payload[INPUT_PROVENANCE_SHADOW_KEY] = '
                                     '_input_provenance_shadow(session, bundle)\n'
                                     '    # 寫檔前先驗：任何 NaN／±inf 數值 → ValueError（此時尚未碰檔案）。\n',
                                     '    payload[REQUIRED_CORE_OK_KEY] = True     # 批 Z66（Q1）：走到這裡 ⇔ '
                                     'Required Core 全部可評估\n'
                                     '    # 寫檔前先驗：任何 NaN／±inf 數值 → ValueError（此時尚未碰檔案）。\n'))}
# <<< C2A_REVERT_PAIRS


def _rel(file_path) -> str:
    p = pathlib.Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def c2a_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 C2a-2 之前的寫法（無 pair 則原樣；只套一次）。

    判定同 dec074／c1（整檔一起看）：各組 `新寫法` 全 1 次 ⇒ 換回；全 0 次 ⇒ 已換回、原樣返回；其餘 ⇒ AssertionError。
    """
    rel = _rel(file_path)
    pairs = C2A_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回（每組 `新寫法` 都含 C2a-2 新增行，換回後必然 0 次）
    assert all(c == 1 for c in counts), (
        f"{rel} C2a-2 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new[:120]!r}"
        code = code.replace(new, old)
    return code


def _exec_as_module(code: str, name: str):
    """原始碼 → 獨立模組物件（不影響本尊；依賴的 L3 模組與本尊共用 ⇒ 同一組 mock 對兩邊同時生效）。"""
    path = REPO / _RC_REL
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(path)
    sys.modules[name] = m                      # dataclass 需要以模組名回查
    exec(compile(code, str(path), "exec"), m.__dict__)
    return m


_PRE: dict = {}


def c2a_pre_module():
    """現行 `risk_cap_apply.py` 只把 C2a-2 改動換回基底 `0a78f308` 寫法（獨立模組物件）。"""
    if "m" not in _PRE:
        code = c2a_revert_for(_RC_REL, (REPO / _RC_REL).read_text(encoding="utf-8"))
        _PRE["m"] = _exec_as_module(code, "_c2a_pre_risk_cap_apply")
    return _PRE["m"]


def c2a_mutant_module(swaps, tag: str):
    """單點突變：現行檔做指定替換（每組恰一處）後載入成獨立模組。"""
    code = (REPO / _RC_REL).read_text(encoding="utf-8")
    for new, old in swaps:
        assert code.count(new) == 1, f"突變點不唯一或已不存在：{new[:100]!r}"
        code = code.replace(new, old)
    return _exec_as_module(code, f"_c2a_mut_{tag}")


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案與舊批次測試
# ══════════════════════════════════════════════════════════════════════════
import ast  # noqa: E402
import copy  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
from datetime import date, datetime, timezone  # noqa: E402

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

import shared.input_provenance_policy as P  # noqa: E402
from shared.risk_cap_policy import RISK_CAP_RULESET_VERSION  # noqa: E402
from src.compute.macro import input_provenance as IP  # noqa: E402
from src.services import macro_engine_inputs as M  # noqa: E402
from src.services import macro_state_locker as MSL  # noqa: E402
from src.services import risk_cap_apply as RC  # noqa: E402
from tests.test_c2a_input_provenance import _inputs  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 10, 14, 2, 0, tzinfo=UTC)          # 台北 2026-10-14（週三）10:00
FIXED_TS = "2026-10-14 10:00:00"
KEY = RC.INPUT_PROVENANCE_SHADOW_KEY
FILES = ("risk_cap_state.json", "macro_state.json")


def _hf_cal():
    from src.data.stock import twse_holiday_fetcher as hf
    payload = json.loads((REPO / "tests/fixtures/twse_holiday_schedule_115_synthetic.json")
                         .read_text(encoding="utf-8"))
    return hf.parse_holiday_schedule(payload, fetched_at=datetime(2026, 10, 2, tzinfo=UTC))


@pytest.fixture
def env(monkeypatch):
    """L1 全 mock（休市表＝fixture、PMI 歷史＝呼叫端指定）＋固定落檔時間戳（兩版逐位比對用）。"""
    cal = _hf_cal()
    monkeypatch.setattr(M._hf, "fetch_twse_holiday_calendar", lambda *, taipei_year: cal)
    holder = {"hist": None, "calls": 0}

    def _load():
        holder["calls"] += 1
        return holder["hist"]
    monkeypatch.setattr(M._mcr, "load_tw_pmi_history", _load)
    monkeypatch.setattr(MSL, "_now_str", lambda: FIXED_TS)

    def _set(hist):
        holder["hist"] = hist
    _set.holder = holder
    return _set


def _session(kw):
    return {"macro_info": kw["macro_info"], "bias_info": kw["bias_info"],
            "m1b_m2_info": kw["m1b_m2_info"], "li_latest": kw["li_latest"],
            "mkt_info": kw["mkt_info"], "unrelated": 1}


def _run(mod, kw, d: pathlib.Path):
    d.mkdir(parents=True, exist_ok=True)
    return mod.compute_and_lock_risk_cap(_session(kw), now=NOW, state_file_path=str(d / "macro_state.json"))


def _strip_shadow_bytes(raw: bytes) -> bytes:
    """現行版落檔 → 去掉觀測欄後以 `_write_state_lock` 同一組參數重新序列化（鍵順序保留）。"""
    st = json.loads(raw.decode("utf-8"))
    assert KEY in st
    st.pop(KEY)
    return json.dumps(st, ensure_ascii=False, indent=4).encode("utf-8")


def _no_tmp(d: pathlib.Path):
    assert not list(d.glob("*.tmp")), list(d.glob("*.tmp"))


def _assert_same_core(pre, cur, d_pre: pathlib.Path, d_cur: pathlib.Path):
    """核心結果逐位相同（觀測欄以外）。回傳現行版落檔的觀測欄（沒寫檔 ⇒ None）。"""
    assert (pre.written, pre.reason, pre.missing_core, pre.files_written, pre.bundle_summary) == \
           (cur.written, cur.reason, cur.missing_core, cur.files_written, cur.bundle_summary)
    _no_tmp(d_pre)
    _no_tmp(d_cur)
    if not cur.written:
        assert KEY not in (cur.engine_result or {})
        assert pre.engine_result == cur.engine_result
        for f in FILES:
            assert not (d_pre / f).exists() and not (d_cur / f).exists(), f
        return None
    er = dict(cur.engine_result)
    shadow = er.pop(KEY)
    assert list(er) == list(pre.engine_result) and er == pre.engine_result
    shadows = []
    for f in FILES:
        b_pre, b_cur = (d_pre / f).read_bytes(), (d_cur / f).read_bytes()
        assert _strip_shadow_bytes(b_cur) == b_pre, f
        shadows.append(json.loads(b_cur.decode("utf-8"))[KEY])
    assert shadows[0] == shadows[1] == shadow
    assert (d_cur / FILES[0]).read_bytes() == (d_cur / FILES[1]).read_bytes()   # 雙寫逐位相同（照舊）
    return shadow


def _pair(env, tmp_path, kw, tag="x", capsys=None):
    env(kw["pmi_history"])
    d_pre, d_cur = tmp_path / f"pre_{tag}", tmp_path / f"cur_{tag}"
    pre = _run(c2a_pre_module(), kw, d_pre)
    out_pre = capsys.readouterr().out if capsys else None
    cur = _run(RC, kw, d_cur)
    out_cur = capsys.readouterr().out if capsys else None
    return pre, cur, d_pre, d_cur, out_pre, out_cur


# ── 情境網格 ────────────────────────────────────────────────────────────────
def _no_pcr_src_col(kw):
    kw["li_latest"] = kw["li_latest"].drop(columns=[P.PCR_SOURCE_COLUMN])
    return kw


_SCENARIOS = {
    "all_fresh_official": lambda: _inputs(),
    "pcr_inst_estimate": lambda: _inputs(pcr_src="FinMind-TXO-inst-est"),
    "pcr_unknown_label": lambda: _inputs(pcr_src="???"),
    "pcr_old_pickle_no_src_col": lambda: _no_pcr_src_col(_inputs()),
    "bias_estimated": lambda: _inputs(bias_extra={"is_estimated": True, "data_days": 120}),
    "bias_flag_missing": lambda: _inputs(bias_extra={"is_estimated": None}),
    "pmi_secondary": lambda: _inputs(pmi_src="StockFeel"),
    "pmi_stale_cache": lambda: _inputs(pmi_src="stale-cache(CIER-EN)"),
    "pmi_unknown_label": lambda: _inputs(pmi_src="Weird"),
    "pmi_is_stale_flag": lambda: _inputs(pmi_extra={"is_stale": True}),
    "li_stale_pickle": lambda: _inputs(li_stale=True),
    "m1b_twii_proxy": lambda: _inputs(m1b_info={"m1b_yoy": 3.0, "m2_yoy": 4.0, "data_month": "2026-08",
                                               "source": "TWII-momentum", "is_proxy": True}),
    "m1b_missing": lambda: _inputs(m1b_info={}),
    "pcr_missing_optional": lambda: _inputs(pcr=None),
    "bias_missing_optional": lambda: _inputs(bias=None),
    "not_below_ma5": lambda: _inputs(below=False),
    "pmi_contraction_veto": lambda: _inputs(pmi=47.0, prev_rows=[(date(2026, 8, 1), 47.5, "CIER")]),
    "futures_veto": lambda: _inputs(fut=-60000.0),
    # ── 不寫檔（三道閘門）────
    "core_vix_missing": lambda: _inputs(vix=None),
    "core_vix_stale": lambda: _inputs(vix_date="2026-09-01"),
    "core_pmi_prev_missing": lambda: _inputs(prev_rows=[(date(2026, 5, 1), 49.0, "CIER")]),
    "core_ma5_missing": lambda: _inputs(below=None),
}


@pytest.mark.parametrize("name", sorted(_SCENARIOS))
def test_before_after_grid(name, env, tmp_path, capsys):
    pre, cur, d_pre, d_cur, out_pre, out_cur = _pair(env, tmp_path, _SCENARIOS[name](), name, capsys)
    shadow = _assert_same_core(pre, cur, d_pre, d_cur)
    assert out_pre == out_cur                       # 成功路徑 ⇒ 觀測欄不多印任何字元
    if name.startswith("core_"):
        assert shadow is None and not cur.written
        assert env.holder["calls"] == 2              # 兩版引擎各讀一次；沒寫檔 ⇒ 觀測欄沒有重讀
    else:
        assert env.holder["calls"] == 3              # 還原體 1 次＋現行版引擎 1 次＋觀測欄重讀 1 次
        assert cur.written and "_error" not in shadow, shadow
        assert shadow["shadow_policy_version"] == P.SHADOW_POLICY_VERSION
        assert list(shadow["inputs"]) == list(P.INPUT_POLICY)
        assert "…[truncated:" not in json.dumps(shadow, ensure_ascii=False)   # 正常值不被截（上限只截異常值）


def test_fail_safe_round_records_nothing(env, tmp_path):
    env(None)
    d_pre, d_cur = tmp_path / "p", tmp_path / "c"
    d_pre.mkdir(), d_cur.mkdir()
    pre = c2a_pre_module().compute_and_lock_risk_cap({}, now=NOW, state_file_path=str(d_pre / "macro_state.json"))
    cur = RC.compute_and_lock_risk_cap({}, now=NOW, state_file_path=str(d_cur / "macro_state.json"))
    assert cur.reason == RC.REASON_FAIL_SAFE
    assert _assert_same_core(pre, cur, d_pre, d_cur) is None
    assert env.holder["calls"] == 2                  # 兩版各讀一次（引擎）；沒寫檔 ⇒ 觀測欄沒有再讀


def _random_cases(n=120):
    rng = random.Random(20261024)
    for i in range(n):
        yield i, _inputs(
            vix=rng.choice([12.0, 21.99, 22.0, 28.0, 35.0, 45.0, None]),
            vix_date=rng.choice(["2026-10-13", "2026-10-12", "2026-10-01"]),
            pmi=rng.choice([45.0, 47.99, 48.0, 50.0, 55.01]),
            pmi_src=rng.choice(["CIER-EN", "NDC", "StockFeel", "stale-cache(CIER)", "Weird", None]),
            prev_rows=rng.choice([None, [(date(2026, 8, 1), 47.0, "CIER")],
                                  [(date(2026, 8, 1), 50.0, "MoneyDJ"), (date(2026, 8, 1), 50.0, "CIER")]]),
            bias=rng.choice([-12.0, 0.0, 16.0, None]),
            bias_extra=rng.choice([None, {"is_estimated": True, "data_days": 90}]),
            pcr=rng.choice([60.0, 100.0, 160.0, None]),
            pcr_src=rng.choice(["TAIFEX", "FinMind-TXO-inst-est"]),
            fut=rng.choice([-60000.0, -21000.0, 3000.0]),
            li_stale=rng.choice([None, True, False]),
            below=rng.choice([True, False, None]))


def test_before_after_random_grid(env, tmp_path):
    written = 0
    for i, kw in _random_cases():
        pre, cur, d_pre, d_cur, _, _ = _pair(env, tmp_path, kw, f"r{i}")
        shadow = _assert_same_core(pre, cur, d_pre, d_cur)
        if cur.written:
            written += 1
            assert "_error" not in shadow, (i, shadow)
            assert "…[truncated:" not in json.dumps(shadow, ensure_ascii=False), i
    assert 20 <= written < 120, written                # 網格同時涵蓋寫檔與不寫檔


def test_reader_outputs_identical(env, tmp_path):
    """讀端（`get_macro_state` 各模式）對「有觀測欄」與「沒有觀測欄」的檔輸出相同。"""
    pre, cur, d_pre, d_cur, _, _ = _pair(env, tmp_path, _inputs(pcr_src="FinMind-TXO-inst-est"))
    assert cur.written
    now = datetime(2026, 10, 14, 3, 0, tzinfo=UTC)
    for strict in (False, True):
        for rv in (False, True):
            for wr in (None, {"health_score": 70.0, "effective_regime": "bull"}):
                a = MSL.get_macro_state(wr, state_file_path=str(d_pre / "macro_state.json"),
                                        strict=strict, require_valid_risk_cap=rv, now=now)
                b = MSL.get_macro_state(wr, state_file_path=str(d_cur / "macro_state.json"),
                                        strict=strict, require_valid_risk_cap=rv, now=now)
                assert a == b, (strict, rv, wr)
    assert MSL.get_macro_state(None, state_file_path=str(d_cur / "macro_state.json"),
                               require_valid_risk_cap=True, now=now)["exposure_limit_pct"] is not None


# ══════════════════════════════════════════════════════════════════════════
# 3. 觀測欄內容
# ══════════════════════════════════════════════════════════════════════════
class TestShadowContent:
    def test_equals_direct_l2_call(self, env, tmp_path):
        kw = _inputs(pcr_src="FinMind-TXO-inst-est", bias_extra={"is_estimated": True, "data_days": 100})
        env(kw["pmi_history"])
        res = _run(RC, kw, tmp_path)
        b = M.build_engine_inputs(**{k: v for k, v in kw.items()}, now=NOW, calendar=_hf_cal().as_sets())
        scored = {k for k, v in b.macro_numbers.items() if v is not None} - set(b.disabled_inputs)
        direct = IP.infer_input_provenance(assessed=b.assessed, scored_keys=scored, **kw)
        assert res.engine_result[KEY] == {"shadow_policy_version": P.SHADOW_POLICY_VERSION, "inputs": direct}
        rec = res.engine_result[KEY]["inputs"]
        assert rec["PCR"]["provenance"] == "proxy" and rec["PCR"]["riskcap_eligible"] is False
        assert rec["PCR"]["actual_scored"] is True       # C2a 不改計分：仍計分 ⇒ shadow 看得出差異
        assert rec["BIAS240_pct"]["provenance"] == "estimated"
        assert rec["M1B_YoY_pct"]["actual_scored"] is False   # 停用 ⇒ ⛔ 不記已計分
        assert rec["ISM_PMI_or_OECD_CLI"]["provenance"] == "official"
        assert rec["PMI_Prev_Month"]["source_id"] == "data.gov.tw:dataset:6100"
        for r in rec.values():
            assert set(r) == set(IP.RECORD_FIELDS)

    def test_pmi_history_reread_via_same_l1(self, env, tmp_path):
        kw = _inputs()
        env(kw["pmi_history"])
        _run(RC, kw, tmp_path)
        assert env.holder["calls"] == 2              # 引擎一次＋觀測欄一次（同一支 L1、同一個 mock）

    def test_constants_and_attached_keys(self):
        assert KEY == "input_provenance_shadow" and KEY in RC.ATTACHED_KEYS
        assert len(set(RC.ATTACHED_KEYS)) == len(RC.ATTACHED_KEYS)
        pre = c2a_pre_module()
        assert tuple(k for k in RC.ATTACHED_KEYS if k != KEY) == pre.ATTACHED_KEYS
        assert isinstance(RC.SHADOW_STR_MAX_LEN, int) and RC.SHADOW_STR_MAX_LEN >= 256
        assert RC.ENGINE_SOURCE == pre.ENGINE_SOURCE == "new_ui_risk_cap_v2"
        assert RISK_CAP_RULESET_VERSION == "risk_cap.v2"
        for name in ("REASON_FAIL_SAFE", "REASON_CORE_MISSING", "REASON_NOT_FINITE", "NONFINITE_TEXT"):
            assert getattr(RC, name) == getattr(pre, name), name
        from shared.risk_cap_history_policy import PRODUCTION_WRITE_APPROVED
        assert PRODUCTION_WRITE_APPROVED is False

    def test_engine_clash_guard_covers_shadow_key(self, env, tmp_path, monkeypatch):
        kw = _inputs()
        env(kw["pmi_history"])
        real = RC.run_rule_engine
        monkeypatch.setattr(RC, "run_rule_engine", lambda b, **k: {**real(b, **k), KEY: "x"})
        with pytest.raises(RuntimeError, match="附帶欄位名"):
            _run(RC, kw, tmp_path)
        assert not (tmp_path / "macro_state.json").exists()

    def test_safe_print_dependency_exists(self):
        from shared import na_drop_log
        assert callable(na_drop_log._safe_print)


# ══════════════════════════════════════════════════════════════════════════
# 4. 失敗注入
# ══════════════════════════════════════════════════════════════════════════
def _assert_marker(shadow, stage, error=None):
    assert set(shadow) <= {"_error", "_stage", "_log_error"}, shadow
    assert shadow["_stage"] == stage, shadow
    assert isinstance(shadow["_error"], str) and shadow["_error"], shadow
    shadow["_error"].encode("ascii")
    if error is not None:
        assert shadow["_error"] == error, shadow


def _inject(env, tmp_path, kw, tag, capsys=None):
    pre, cur, d_pre, d_cur, _, out = _pair(env, tmp_path, kw, tag, capsys)
    assert cur.written and pre.written
    return _assert_same_core(pre, cur, d_pre, d_cur), out


class TestFailureInjection:
    def test_a_infer_raises(self, env, tmp_path, monkeypatch, capsys):
        def boom(**_k):
            raise RuntimeError("upstream secret \ud800")
        monkeypatch.setattr(IP, "infer_input_provenance", boom)
        shadow, out = _inject(env, tmp_path, _inputs(), "a", capsys)
        _assert_marker(shadow, "infer", "RuntimeError")
        assert "secret" not in json.dumps(shadow)
        assert f"{KEY} 觀測失敗（階段 infer：RuntimeError）" in out

    # `from src.data.macro import macro_cache_reader`：子模組已是套件屬性 ⇒ 要讓**套件** import 失敗才擋得到。
    @pytest.mark.parametrize("mod", ["src.compute.macro.input_provenance", "shared.input_provenance_policy",
                                     "src.data.macro"])
    def test_b_import_fails(self, mod, env, tmp_path, monkeypatch, capsys):
        kw = _inputs()
        env(kw["pmi_history"])
        # 引擎先跑完（`M._mcr` 已綁定），再讓觀測欄的延遲 import 失敗
        real_engine = RC.run_rule_engine

        def _engine_then_break(b, **k):
            out = real_engine(b, **k)
            monkeypatch.setitem(sys.modules, mod, None)
            return out
        monkeypatch.setattr(RC, "run_rule_engine", _engine_then_break)
        d_pre, d_cur = tmp_path / "pre", tmp_path / "cur"
        pre = _run(c2a_pre_module(), kw, d_pre)
        capsys.readouterr()
        cur = _run(RC, kw, d_cur)
        monkeypatch.undo()          # 換回原模組物件（⛔ 不重新 import：會換掉套件屬性、污染其他測試）
        shadow = _assert_same_core(pre, cur, d_pre, d_cur)
        _assert_marker(shadow, "import")
        assert shadow["_error"] in ("ImportError", "ModuleNotFoundError")
        assert "階段 import" in capsys.readouterr().out

    def test_c_lone_surrogate_source(self, env, tmp_path, capsys):
        kw = _inputs()
        kw["macro_info"]["vix"]["source"] = "yfinance\ud800"
        shadow, out = _inject(env, tmp_path, kw, "c", capsys)
        _assert_marker(shadow, "validate", "UnicodeEncodeError")
        assert "階段 validate：UnicodeEncodeError" in out

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_d_nonfinite_in_shadow(self, bad, env, tmp_path, monkeypatch):
        monkeypatch.setattr(IP, "infer_input_provenance", lambda **_k: {"VIX_Index": {"x": bad}})
        shadow, _ = _inject(env, tmp_path, _inputs(), "d")
        _assert_marker(shadow, "validate", "ValueError")

    def test_e_huge_string_truncated(self, env, tmp_path):
        kw = _inputs()
        kw["macro_info"]["vix"]["source"] = "x" * 200_000
        shadow, _ = _inject(env, tmp_path, kw, "e")
        assert "_error" not in shadow
        sid = shadow["inputs"]["VIX_Index"]["source_id"]
        assert sid == "x" * RC.SHADOW_STR_MAX_LEN + "…[truncated:200000]"
        assert (tmp_path / "cur_e" / "macro_state.json").stat().st_size < 60_000
        for r in shadow["inputs"].values():
            for v in r.values():
                assert not isinstance(v, str) or len(v) <= RC.SHADOW_STR_MAX_LEN + 32

    def test_f_pmi_reread_raises(self, env, tmp_path, monkeypatch, capsys):
        kw = _inputs()
        env(kw["pmi_history"])
        calls = {"n": 0}

        def _load():
            calls["n"] += 1
            if calls["n"] == 2:                       # 第 1 次＝現行版引擎；第 2 次＝觀測欄重讀
                raise OSError("parquet 讀到一半")
            return kw["pmi_history"]
        d_pre, d_cur = tmp_path / "pre", tmp_path / "cur"
        pre = _run(c2a_pre_module(), kw, d_pre)       # 還原體沒有重讀（用 env 預設 mock）
        monkeypatch.setattr(M._mcr, "load_tw_pmi_history", _load)
        capsys.readouterr()
        cur = _run(RC, kw, d_cur)
        assert calls["n"] == 2
        _assert_marker(_assert_same_core(pre, cur, d_pre, d_cur), "pmi_history", "OSError")
        assert "階段 pmi_history：OSError" in capsys.readouterr().out

    def test_non_json_type(self, env, tmp_path, monkeypatch):
        import numpy as np
        monkeypatch.setattr(IP, "infer_input_provenance", lambda **_k: {"VIX_Index": {"x": np.int64(3)}})
        shadow, _ = _inject(env, tmp_path, _inputs(), "nj")
        _assert_marker(shadow, "sanitize", "TypeError")

    def test_session_get_raises(self, env, tmp_path):
        """session 的 `.get` 在引擎讀完之後才壞 ⇒ 只影響觀測欄。"""
        kw = _inputs()
        env(kw["pmi_history"])

        class _Sess(dict):
            n = 0

            def get(self, k, default=None):
                _Sess.n += 1
                if _Sess.n > 5:
                    raise KeyError("boom")
                return super().get(k, default)
        d_pre, d_cur = tmp_path / "pre", tmp_path / "cur"
        d_pre.mkdir(), d_cur.mkdir()
        pre = c2a_pre_module().compute_and_lock_risk_cap(_Sess(_session(kw)), now=NOW,
                                                         state_file_path=str(d_pre / "macro_state.json"))
        _Sess.n = 0
        cur = RC.compute_and_lock_risk_cap(_Sess(_session(kw)), now=NOW,
                                           state_file_path=str(d_cur / "macro_state.json"))
        _assert_marker(_assert_same_core(pre, cur, d_pre, d_cur), "session", "KeyError")


class _Broken:
    encoding = "utf-8"

    def __init__(self, exc):
        self.exc = exc

    def write(self, *_a):
        raise self.exc

    def flush(self):
        raise self.exc


def _ascii_stdout():
    return io.TextIOWrapper(io.BytesIO(), encoding="ascii", errors="strict")


class TestShadowLogUnsafeStdout:
    """(g) 觀測欄失敗、而且 log 時 stdout 壞掉 ⇒ 照樣寫檔；全部管道都壞 ⇒ `_log_error` 留痕。"""

    @pytest.fixture
    def failing_infer(self, monkeypatch):
        def boom(**_k):
            raise RuntimeError("x")
        monkeypatch.setattr(IP, "infer_input_provenance", boom)

    @pytest.mark.parametrize("kind", ["broken_pipe", "closed", "ascii", "none"])
    def test_stdout_bad(self, kind, failing_infer, env, tmp_path, monkeypatch):
        kw = _inputs()
        env(kw["pmi_history"])
        d_pre, d_cur = tmp_path / "pre", tmp_path / "cur"
        pre = _run(c2a_pre_module(), kw, d_pre)
        bad = {"broken_pipe": _Broken(BrokenPipeError(32, "Broken pipe")),
               "closed": _Broken(ValueError("I/O operation on closed file")),
               "ascii": _ascii_stdout(), "none": None}[kind]
        err = io.StringIO()
        saved = sys.stdout
        monkeypatch.setattr(sys, "__stderr__", err)
        sys.stdout = bad
        try:
            cur = _run(RC, kw, d_cur)
        finally:
            sys.stdout = saved
        shadow = _assert_same_core(pre, cur, d_pre, d_cur)
        _assert_marker(shadow, "infer", "RuntimeError")
        assert "_log_error" not in shadow
        if kind == "ascii":
            bad.flush()
            assert b"input_provenance_shadow" in bad.buffer.getvalue()
        else:
            assert "input_provenance_shadow" in err.getvalue()

    def test_every_channel_broken_leaves_log_error(self, failing_infer, env, tmp_path, monkeypatch):
        kw = _inputs()
        env(kw["pmi_history"])
        d_pre, d_cur = tmp_path / "pre", tmp_path / "cur"
        pre = _run(c2a_pre_module(), kw, d_pre)
        saved = sys.stdout
        monkeypatch.setattr(sys, "__stderr__", _Broken(RuntimeError("stderr also broken")))
        sys.stdout = _Broken(RuntimeError("reentrant"))
        try:
            cur = _run(RC, kw, d_cur)
        finally:
            sys.stdout = saved
        shadow = _assert_same_core(pre, cur, d_pre, d_cur)
        _assert_marker(shadow, "infer", "RuntimeError")
        assert shadow["_log_error"] == "RuntimeError"

    def test_safe_print_import_fails_leaves_log_error(self, failing_infer, env, tmp_path, monkeypatch):
        kw = _inputs()
        env(kw["pmi_history"])
        d_pre, d_cur = tmp_path / "pre", tmp_path / "cur"
        pre = _run(c2a_pre_module(), kw, d_pre)
        monkeypatch.setitem(sys.modules, "shared.na_drop_log", None)   # teardown 換回原模組物件
        cur = _run(RC, kw, d_cur)
        monkeypatch.undo()
        shadow = _assert_same_core(pre, cur, d_pre, d_cur)
        assert shadow["_log_error"] in ("ImportError", "ModuleNotFoundError")


# ══════════════════════════════════════════════════════════════════════════
# 5. 唯讀
# ══════════════════════════════════════════════════════════════════════════
def test_does_not_mutate_session_bundle_engine(env, tmp_path, monkeypatch):
    kw = _inputs(pcr_src="FinMind-TXO-inst-est")
    env(kw["pmi_history"])
    sess = _session(kw)
    snap = {k: copy.deepcopy(v) for k, v in sess.items() if k != "li_latest"}
    li_snap = sess["li_latest"].copy()
    seen = {}
    real_load, real_engine = RC.load_engine_inputs_from_session, RC.run_rule_engine

    def _load(s, **k):
        b = real_load(s, **k)
        seen["bundle"], seen["bundle_snap"] = b, (dict(b.macro_numbers), dict(b.assessed),
                                                  b.disabled_inputs, dict(b.input_asof))
        return b

    def _engine(b, **k):
        out = real_engine(b, **k)
        seen["engine"], seen["engine_snap"] = out, copy.deepcopy(out)
        return out
    monkeypatch.setattr(RC, "load_engine_inputs_from_session", _load)
    monkeypatch.setattr(RC, "run_rule_engine", _engine)
    res = RC.compute_and_lock_risk_cap(sess, now=NOW, state_file_path=str(tmp_path / "macro_state.json"))
    assert res.written and KEY in res.engine_result
    assert {k: v for k, v in sess.items() if k != "li_latest"} == snap
    pd.testing.assert_frame_equal(sess["li_latest"], li_snap)
    b = seen["bundle"]
    assert (dict(b.macro_numbers), dict(b.assessed), b.disabled_inputs, dict(b.input_asof)) == seen["bundle_snap"]
    assert seen["engine"] == seen["engine_snap"] and KEY not in seen["engine"]


# ══════════════════════════════════════════════════════════════════════════
# 6. 讀者守衛
# ══════════════════════════════════════════════════════════════════════════
def _product_files():
    files = [REPO / "app.py"] + [p for d in ("src", "shared", "scripts") for p in (REPO / d).rglob("*.py")]
    return [p for p in files if "__pycache__" not in p.parts]


def test_no_production_reader_of_shadow():
    pat = re.compile(r"input_provenance_shadow|INPUT_PROVENANCE_SHADOW_KEY")
    hits = sorted(p.relative_to(REPO).as_posix() for p in _product_files()
                  if pat.search(p.read_text(encoding="utf-8")))
    assert hits == [_RC_REL], hits


def test_risk_cap_apply_never_reads_shadow_back():
    """寫端自己也只寫不讀：觀測欄鍵只出現在一次 subscript 賦值（與常數定義／ATTACHED_KEYS）。"""
    tree = ast.parse((REPO / _RC_REL).read_text(encoding="utf-8"))
    loads = [n for n in ast.walk(tree) if isinstance(n, ast.Subscript)
             and isinstance(n.ctx, ast.Load) and ast.unparse(n.slice) == "INPUT_PROVENANCE_SHADOW_KEY"]
    stores = [n for n in ast.walk(tree) if isinstance(n, ast.Subscript)
              and isinstance(n.ctx, ast.Store) and ast.unparse(n.slice) == "INPUT_PROVENANCE_SHADOW_KEY"]
    assert not loads and len(stores) == 1


def test_risk_cap_apply_forbidden_literals():
    text = (REPO / _RC_REL).read_text(encoding="utf-8")
    for bad in ("_pcr_src", "PCR_SOURCE_COLUMN", "is_proxy"):     # session_state（程式碼部分）由 z65 test_layering 守
        assert bad not in text, bad


def test_shadow_imports_are_lazy():
    """新模組只在觀測欄函式內 import（稽核第 3 點）：module 層級沒有。"""
    tree = ast.parse((REPO / _RC_REL).read_text(encoding="utf-8"))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    mods = {n.module for n in top if isinstance(n, ast.ImportFrom)} | {
        a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    for lazy in ("shared.input_provenance_policy", "src.compute.macro.input_provenance",
                 "src.data.macro.macro_cache_reader", "src.data.macro", "shared.na_drop_log"):
        assert lazy not in mods, lazy


# ══════════════════════════════════════════════════════════════════════════
# 7. 突變自驗（恰一次字面替換 → 守衛必須轉紅）
# ══════════════════════════════════════════════════════════════════════════
def test_mutation_without_utf8_selfcheck_fails_round_and_leaves_tmp(env, tmp_path):
    mod = c2a_mutant_module([('        json.dumps(shadow, ensure_ascii=False, allow_nan=False).encode("utf-8")\n',
                              '        json.dumps(shadow, ensure_ascii=False, allow_nan=False)\n')], "noenc")
    kw = _inputs()
    kw["macro_info"]["vix"]["source"] = "yfinance\ud800"
    env(kw["pmi_history"])
    with pytest.raises(UnicodeEncodeError):
        _run(mod, kw, tmp_path / "m")
    assert list((tmp_path / "m").glob("*.tmp"))          # 原版 test_c_lone_surrogate_source 的 `.tmp` 守衛必紅


def test_mutation_without_except_fails_round(env, tmp_path, monkeypatch):
    mod = c2a_mutant_module([("    except Exception as exc:  # noqa: BLE001 — 觀測欄失敗",
                              "    except ZeroDivisionError as exc:  # noqa: BLE001 — 觀測欄失敗")], "noexc")

    def boom(**_k):
        raise RuntimeError("x")
    monkeypatch.setattr(IP, "infer_input_provenance", boom)
    env(_inputs()["pmi_history"])
    with pytest.raises(RuntimeError):
        _run(mod, _inputs(), tmp_path / "m")
    assert not (tmp_path / "m" / "macro_state.json").exists()


# ══════════════════════════════════════════════════════════════════════════
# 1. 還原鏈
# ══════════════════════════════════════════════════════════════════════════
def test_c2a_revert_is_exact_base_source():
    assert set(C2A_REVERT_PAIRS) == set(C2A_BASE_SHA)
    for rel in sorted(C2A_REVERT_PAIRS):
        code = c2a_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == C2A_BASE_SHA[rel], rel


def test_c2a_revert_is_idempotent():
    for rel in sorted(C2A_REVERT_PAIRS):
        once = c2a_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert c2a_revert_for(rel, once) == once, rel


def test_chain_head_is_before_c1():
    """`c1_revert_for` 開頭先套 C2a-2 ⇒ 所有串到 c1 的舊批次鏈（dec074／vn1store／c21／z66b…）都先換回本批。"""
    from tests.test_c1_observability import c1_revert_for
    cur = (REPO / _RC_REL).read_text(encoding="utf-8")
    assert c1_revert_for(_RC_REL, cur) == c2a_revert_for(_RC_REL, cur)
    from tests.test_batch_c21 import C21_BASE_SHA, c21_revert_for
    code = c21_revert_for(_RC_REL, cur)
    assert hashlib.sha256(code.encode("utf-8")).hexdigest() == C21_BASE_SHA[_RC_REL]
