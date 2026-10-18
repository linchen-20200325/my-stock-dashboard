"""UIA-01 / UIA-02 / UIA-07 —— 三個 P0 資料狀態正確性修正的回歸測試（2026-10-18）。

· UIA-01：部分總經資料被說成「五桶全綠」／🟢 運作中。
    → `tab_macro_v2.bucket_summary` 多帶 `n_no_value`；`overall_verdict` 有燈沒值時不再印「五桶全綠」、
      改揭露「只根據 N／M 項有資料」；`band` 一位未動（DEC-046 / BP-DR-19 未裁示，⛔ 不改燈色）。
      新 UI 危險度卡（卡② + 三欄摘要「風險」格）在 N < M 時走既有 `UI_PARTIAL`，⛔ 不畫運作中。
· UIA-02：來源回 0 列／None 在「憑什麼 › 資料體檢」被畫成 🟢 運作中。
    → L0 `shared.fetch_monitor.has_content`（自 `macro_refresh_service._has_content` 下沉）＋
      `@monitored` 附加欄 `last_has_content`；`page_why` ok＋空 → 灰 `UI_EMPTY`（⛔ 不綠、⛔ 不紅）。
· UIA-07：按過更新而紅綠燈步驟失敗後，「能不能出手」仍顯示灰色「還沒有人叫過」。
    → `tab_today.classify_macro_contract(attempt=)`；失敗 → 紅 `UI_FAILED` ＋ 原因；跳過 → 灰 `UI_EMPTY`；
      沒給 attempt → 輸出與修前逐一相同；有效契約永遠優先。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
# 0. 還原鏈（同 Z62／Z65／Z66／Z66b／C21 慣例）：把本批改動換回 d3425a91（UIA 之前）的寫法
#    `tests/test_batch_c21.py::c21_revert_for` 先呼叫 `uia_revert_for`，再套 C21 自己的還原組
#    ⇒ 舊批次以「修前原始碼」重建模組的守衛照舊成立。
#    ⚠️ 本段只用標準庫，且在任何專案 import 之前（舊批次測試檔會回頭 import 這裡）。
#    還原組由 difflib 對 `git show d3425a91:<rel>` 自動產生（⛔ 手改會讓 sha 對不上）；sha 寫死以免測試依賴 git。
# ══════════════════════════════════════════════════════════════════
REPO = Path(__file__).resolve().parents[1]

UIA_BASE_SHA = {
    'src/services/macro_refresh_service.py': 'fe6962c8dcb8a6945b827b5d6da99fc3d242db7a613c8cee26c554e98e0edd1e',
    'src/ui/views/page_today.py': 'b5591a3bfec52c91e674dc806f45452e150b79bba57822fe3e7643a5994290da',
    'src/ui/views/page_why.py': '7e0ab9960c2b7c11c36302b447974abb91ea989654668afc40aac7f8aff51e82',
}
UIA_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    'src/services/macro_refresh_service.py': (
        ('\nfrom shared.fetch_monitor import has_content\nfrom shared.macro_compute import tw_now_str\n',
         '\nfrom shared.macro_compute import tw_now_str\n'),
        ('\n#: UIA-02（2026-10-18）：判空規則下沉到 L0 `shared.fetch_monitor.has_content`（規則一字未改），\n#: 讓「今天」頁的更新報告與「憑什麼」頁的資料體檢**用同一支判空**（兩把尺會漂開）。\n#: 舊私有名保留為別名（本檔 `audit_source_contents` 照舊呼叫它；突變測試可照舊拔它）。\n_has_content = has_content\n\n',
         '\ndef _has_content(value: Any) -> bool:\n    """一個取回來的東西**算不算有資料**。\n\n    三種形狀分別判，理由寫在這裡以免下一個人「順手統一成 `bool(value)`」：\n      · **DataFrame / Series**（有 `.empty`）：空表 ＝ 沒資料。\n        `bool(df)` 在 pandas 會直接 `ValueError`，不能用真假值判。\n      · **容器**（dict / list / str …）：長度 0 ＝ 沒資料。\n      · **純量**（例如融資餘額的 `float`）：**只認 `None` 是沒資料**。\n        ⚠️ 刻意**不**用 `bool()` —— `0.0` 是一個合法的數值，把它判成\n        「沒資料」等於本檔自己發明一條 fetcher 沒有宣告的規則（§1）。\n        缺值的界線由 fetcher 決定，而它們缺值時回的是 `None`。\n    """\n    if value is None:\n        return False\n    _empty = getattr(value, "empty", None)\n    if _empty is not None:\n        return not bool(_empty)\n    if isinstance(value, (dict, list, tuple, set, frozenset, str, bytes)):\n        return len(value) > 0\n    return True\n\n'),
    ),
    'src/ui/views/page_today.py': (
        ('    classify_macro_contract,\n    macro_attempt_applies,       # UIA-07\n    macro_attempt_failed_reason,  # UIA-07\n    macro_attempt_failed_why,     # UIA-07\n    MACRO_ATTEMPT_FAILED,         # UIA-07\n    MACRO_ATTEMPT_OK,             # UIA-07\n    MACRO_ATTEMPT_SKIPPED,        # UIA-07\n    scrub_state_glyphs,\n',
         '    classify_macro_contract,\n    scrub_state_glyphs,\n'),
        ('\ndef warroom_attempt(report: Any) -> tuple[str, str] | None:\n    """UIA-07：本 session 上一次「更新今日戰情」報告裡 `STEP_WARROOM` 那一步 → `(status, reason)`。\n\n    沒有報告（新 session、還沒按過）/ 報告裡沒有這一步 → None（⛔ 不猜；卡片維持修前的判態）。\n    `reason` 先過 `scrub_secrets`（上游例外原文可能帶金鑰；它會被畫上卡面）。\n    舊格式報告（熱重載後殘留、欄位缺）→ `getattr` 讀不到就當沒有這一步，⛔ 不炸整頁。\n    """\n    if report is None:\n        return None\n    from src.services.macro_refresh_service import STEP_WARROOM\n    for _step in tuple(getattr(report, "steps", ()) or ()):\n        if getattr(_step, "name", None) != STEP_WARROOM:\n            continue\n        _reason = scrub_secrets(str(getattr(_step, "detail", "") or ""))\n        if getattr(_step, "skipped", False):\n            return MACRO_ATTEMPT_SKIPPED, _reason\n        if not getattr(_step, "ok", False):\n            return MACRO_ATTEMPT_FAILED, _reason\n        return MACRO_ATTEMPT_OK, _reason\n    return None\n\n\ndef contract_attempted(regime: Mapping[str, Any] | None,\n',
         '\ndef contract_attempted(regime: Mapping[str, Any] | None,\n'),
        ('def contract_attempted(regime: Mapping[str, Any] | None,\n                       *, error: Any = None, attempt: Any = None) -> bool:\n    """L3 總經契約**這一輪有沒有被叫過**（卡① 的 gate 旗標）。\n',
         'def contract_attempted(regime: Mapping[str, Any] | None,\n                       *, error: Any = None) -> bool:\n    """L3 總經契約**這一輪有沒有被叫過**（卡① 的 gate 旗標）。\n'),
        ('    **永不回 None**，於是那個運算式恆為 True → 卡① 沒有 idle 態。\n\n    UIA-07：`attempt=`（`warroom_attempt()` 的輸出）原樣轉交 —— 本頁按鈕按過 ⇒ 不再是 idle。\n    """\n',
         '    **永不回 None**，於是那個運算式恆為 True → 卡① 沒有 idle 態。\n    """\n'),
        ('    """\n    return classify_macro_contract(regime, error=error, attempt=attempt) != UI_IDLE\n\n',
         '    """\n    return classify_macro_contract(regime, error=error) != UI_IDLE\n\n'),
        ('\n#: UIA-01（2026-10-18）：危險度卡在「有燈沒值」時的口徑揭露列（標籤與值）。\nDANGER_BASIS_FACT_KEY: str = "計算口徑"\nDANGER_BASIS_TEMPLATE: str = (\n    "分母為全部 {m} 項（含未接線）；分子 {n} 項 ＝ 本輪有值的燈"\n    "（含門檻已失準與代理值；代理值只顯示不計分）")\n#: UIA-01：危險度卡在「有燈沒值」時，原本放大字區的結論改掛這一列（非 live 不得帶 `value`）。\nDANGER_DETAIL_FACT_KEY: str = "彙總結果"\n\n\ndef danger_completeness(danger: Any) -> tuple[int, int] | None:\n    """危險度讀數的 `(N, M)`；舊形狀 `(band, detail)`（或第三元素不是兩個整數）→ None。\n\n    None ＝ 呼叫端沒帶完整度 ⇒ 當資料齊全處理（＝ 修前行為；只為手組讀數的向下相容）。\n    """\n    if danger is None or len(danger) < 3:\n        return None\n    _cov = danger[2]\n    try:\n        _n, _m = int(_cov[0]), int(_cov[1])\n    except (TypeError, ValueError, IndexError) as _e:\n        # §1：形狀不對 ⇒ 出聲（log），不猜一組數字；退回修前行為。\n        print(f"[views/page_today] 危險度完整度形狀不對 {_cov!r}：{_e!r} —— 當作沒帶")\n        return None\n    return _n, _m\n\n\ndef _danger_tile(*, key: str, label: str,\n',
         '\ndef _danger_tile(*, key: str, label: str,\n'),
        ('def _danger_tile(*, key: str, label: str,\n                 danger: tuple[str, str] | tuple[str, str, tuple[int, int]] | None,\n                 danger_error: str,\n                 danger_requested: bool, danger_source: str,\n',
         'def _danger_tile(*, key: str, label: str,\n                 danger: tuple[str, str] | None, danger_error: str,\n                 danger_requested: bool, danger_source: str,\n'),
        ('    )\n    _cov = danger_completeness(danger)\n    if _danger_state == UI_LIVE:\n',
         '    )\n    if _danger_state == UI_LIVE:\n'),
        ('            _dfacts = (("燈號", f"{L4_LABEL_UNAVAILABLE}`{scrub_secrets(l4_error)}`"),)\n        if _cov is not None and _cov[0] < _cov[1]:\n            # 📌 UIA-01（2026-10-18）：有燈沒值 ⇒ ⛔ 不畫「🟢 運作中」—— 改走既有的 `UI_PARTIAL`\n            #   （「N／M 計入」）。燈號頻道（`_zh` / `_hex`）**照舊**，worst-of 一位未動（改燈色是\n            #   BP-DR-19 的事，未裁示）。非 live 不得帶 `value` ⇒ 結論改掛 fact（同 degraded 燈卡\n            #   把「現值」掛 fact 的走法），並在卡上寫明分子分母的口徑。\n            _n, _m = _cov\n            _now = (f"**指標危險度：{_zh}\u3000·\u3000只根據 {_n}／{_m} 項有資料**" if _zh\n                    else f"**指標危險度：只根據 {_n}／{_m} 項有資料**")\n            return Tile(\n                Card(key=key, label=label, state=UI_PARTIAL,\n                     note=Note(\n                         now=_now,\n                         why=(f"{_m} 項裡有 {_m - _n} 項本輪沒有值（無資料／未接線／故障），"\n                              f"這張卡的燈只彙總了有值的 {_n} 項 —— "\n                              "**沒有值不等於沒有踩線**，所以不畫成「運作中」"),\n                         where=EXIT_RETRY_HERE)),\n                signal_text=_zh, signal_color=_hex,\n                facts=((DANGER_DETAIL_FACT_KEY, str(danger[1])),\n                       (DANGER_BASIS_FACT_KEY, DANGER_BASIS_TEMPLATE.format(n=_n, m=_m)),\n                       *_dfacts))\n        return Tile(\n',
         '            _dfacts = (("燈號", f"{L4_LABEL_UNAVAILABLE}`{scrub_secrets(l4_error)}`"),)\n        return Tile(\n'),
        ('def build_verdict_tiles(*, alloc: Any, alloc_error: str,\n                        danger: tuple[Any, ...] | None, danger_error: str,\n                        danger_requested: bool,\n',
         'def build_verdict_tiles(*, alloc: Any, alloc_error: str,\n                        danger: tuple[str, str] | None, danger_error: str,\n                        danger_requested: bool,\n'),
        ('                        band_zh_color: Mapping[str, tuple[str, str]] | None = None,\n                        l4_error: str = "",\n                        macro_attempt: tuple[str, str] | None = None) -> tuple[Tile, ...]:\n    """葉1 ① 今日結論 —— **三張並排的卡，沒有第四張「合成結論」**。\n',
         '                        band_zh_color: Mapping[str, tuple[str, str]] | None = None,\n                        l4_error: str = "") -> tuple[Tile, ...]:\n    """葉1 ① 今日結論 —— **三張並排的卡，沒有第四張「合成結論」**。\n'),
        ('            `_load_danger()` 的三個回傳 ＋ 五桶的 gate 旗標。\n            `danger` 是 `overall_verdict()` 的 `(band, detail)`，**不含方向**；\n            UIA-01 起 `_load_danger()` 多帶第三元素 `(N, M)`（兩元素舊形狀照收）。\n        regime / regime_error: `_load_regime()` 的兩個回傳（市場位階契約）。\n',
         '            `_load_danger()` 的三個回傳 ＋ 五桶的 gate 旗標。\n            `danger` 是 `overall_verdict()` 的 `(band, detail)`，**不含方向**。\n        regime / regime_error: `_load_regime()` 的兩個回傳（市場位階契約）。\n'),
        ('        l4_error: L4 載入失敗時的 `repr(e)`。\n        macro_attempt: UIA-07（2026-10-18）`warroom_attempt()` 的輸出（本頁按鈕上一次更新的\n            紅綠燈步驟）。只影響「契約仍未評估」時卡① / 卡③ 的判態與文案；預設 None ⇒ 與修前逐一相同。\n\n',
         '        l4_error: L4 載入失敗時的 `repr(e)`。\n\n'),
        ('    #  帶下來的 —— 同一次仲裁的兩個出口，不會一個叫過一個沒叫過）。\n    _regime_state = classify_macro_contract(regime, error=regime_error or None,\n                                            attempt=macro_attempt)\n    # UIA-07：上一次更新的紅綠燈步驟失敗（且契約仍未評估）→ 原因；否則 None。\n    _att_fail = macro_attempt_failed_reason(regime, error=regime_error or None,\n                                            attempt=macro_attempt)\n    _att_applies = macro_attempt_applies(regime, error=regime_error or None,\n                                         attempt=macro_attempt)\n\n',
         '    #  帶下來的 —— 同一次仲裁的兩個出口，不會一個叫過一個沒叫過）。\n    _regime_state = classify_macro_contract(regime, error=regime_error or None)\n\n'),
        ('    #    `contract_attempted()` 的 docstring）。\n    _alloc_loaded = bool(getattr(alloc, "is_loaded", False))\n    _alloc_state = classify_ui_state(\n',
         '    #    `contract_attempted()` 的 docstring）。\n    _alloc_state = classify_ui_state(\n'),
        ('        requested=(bool(alloc_error)\n                   or contract_attempted(regime, error=regime_error or None,\n                                         attempt=macro_attempt)),\n        # UIA-07：契約未評估是因為上一次更新的紅綠燈步驟失敗 ⇒ 紅（⛔ 不再畫成「還沒有人叫過」）。\n        error=(alloc_error or (None if _alloc_loaded else _att_fail) or None),\n        has_value=_alloc_loaded,\n    )\n',
         '        requested=(bool(alloc_error)\n                   or contract_attempted(regime, error=regime_error or None)),\n        error=alloc_error or None,\n        has_value=bool(getattr(alloc, "is_loaded", False)),\n    )\n'),
        ('            _why = _error_why(SRC_ALLOCATION, alloc_error)\n        elif _att_fail is not None:\n            # UIA-07：失敗路徑的 why ＝ 那一步的原因（⛔ 不是「還沒有人叫過」）。\n            _why = macro_attempt_failed_why(_att_fail)\n        elif _alloc_state == UI_IDLE:\n',
         '            _why = _error_why(SRC_ALLOCATION, alloc_error)\n        elif _alloc_state == UI_IDLE:\n'),
        ('            _why = _alloc_unloaded_why(regime)\n            if _att_applies:\n                # UIA-07：按過更新、沒有失敗、但契約仍未評估 ⇒ 把那一步的原因放在最前面。\n                #   （`_att_applies` 為真 ⇒ `macro_attempt` 必不為 None。）\n                _reason = scrub_state_glyphs(macro_attempt[1])[0] if macro_attempt else ""\n                _why = f"已按過更新：{_reason or \'紅綠燈這一步沒有給原因\'}；" + _why\n        # 📌 批 Z60 QA（有意識的修改，不是漏刪）：非錯誤分支的出口原為 `EXIT_OUT_OF_REACH`\n',
         '            _why = _alloc_unloaded_why(regime)\n        # 📌 批 Z60 QA（有意識的修改，不是漏刪）：非錯誤分支的出口原為 `EXIT_OUT_OF_REACH`\n'),
        ('                why=(upstream_error_why(scrub_secrets(regime_error)) if regime_error else\n                     # UIA-07：紅的是上一次更新的紅綠燈步驟（⛔ 不是讀契約拋例外）。\n                     macro_attempt_failed_why(_att_fail) if _att_fail is not None else\n                     "L3 canonical 契約四條來源本輪皆無值 → 回 `unknown`，"\n',
         '                why=(upstream_error_why(scrub_secrets(regime_error)) if regime_error else\n                     "L3 canonical 契約四條來源本輪皆無值 → 回 `unknown`，"\n'),
        ('\ndef _load_danger(readout: MacroReadout\n                 ) -> tuple[tuple[str, str, tuple[int, int]] | None, str, str]:\n    """**指標危險度那一半**（16 盞燈 worst-of）。回 `((band, detail, (N, M)), err, 出處)`。\n\n    📌 UIA-01（2026-10-18）：讀數多帶第三元素 `(N, M)` ＝ `tab_macro_v2.summary_coverage()`\n    （有值的列數 / 全部列數，與 `overall_verdict` 內部用的是**同一支**）。`_danger_tile()` 照舊\n    也收兩元素 `(band, detail)` 的舊形狀（手組讀數的相容：當資料齊全處理，＝ 修前行為）。\n\n',
         '\ndef _load_danger(readout: MacroReadout) -> tuple[tuple[str, str] | None, str, str]:\n    """**指標危險度那一半**（16 盞燈 worst-of）。回 `((band, detail), err, 出處)`。\n\n'),
        ('        from src.ui.tabs.tab_macro_v2 import (\n            build_rows, bucket_summary, overall_verdict, summary_coverage,\n        )\n',
         '        from src.ui.tabs.tab_macro_v2 import (\n            build_rows, bucket_summary, overall_verdict,\n        )\n'),
        ('        )\n        _summary = bucket_summary(build_rows(dict(readout.readiness)))\n        _band, _detail = overall_verdict(_summary)\n        return (_band, _detail, summary_coverage(_summary)), "", ""\n    except Exception as _e:  # noqa: BLE001\n',
         '        )\n        return overall_verdict(\n            bucket_summary(build_rows(dict(readout.readiness)))), "", ""\n    except Exception as _e:  # noqa: BLE001\n'),
        ('def build_summary_tiles(cards: Sequence[Card], *,\n                        danger: tuple[Any, ...] | None, danger_error: str,\n                        danger_requested: bool,\n',
         'def build_summary_tiles(cards: Sequence[Card], *,\n                        danger: tuple[str, str] | None, danger_error: str,\n                        danger_requested: bool,\n'),
        ('    _alerts, _scanned, _alerts_err = _load_key_alerts(_session)\n    # UIA-07：本 session 上一次「更新今日戰情」的紅綠燈步驟（沒按過 → None ⇒ 判態與修前相同）。\n    try:\n        _attempt = warroom_attempt(_session.get(SS_REFRESH_REPORT))\n    except Exception as _e:  # noqa: BLE001 — 讀不出來就當沒有，log 出聲（⛔ 不炸整頁、⛔ 不猜）\n        print(f"[views/page_today] 讀不出上一次更新的紅綠燈步驟：{_e!r} —— 當作沒有")\n        _attempt = None\n\n',
         '    _alerts, _scanned, _alerts_err = _load_key_alerts(_session)\n\n'),
        ('    _blocks = {_b.key: _b for _b in build_today_blocks(\n        macro_state=_regime, macro_error=scrub_secrets(_regime_err) or None,\n        macro_attempt=_attempt)}\n\n',
         '    _blocks = {_b.key: _b for _b in build_today_blocks(\n        macro_state=_regime, macro_error=scrub_secrets(_regime_err) or None)}\n\n'),
        ('    #    `EXIT_RETRY_HERE`（對面那句 Z60 起在本頁不成立）；其餘欄位原物件照用。\n    _bar_cards = build_status_bar_cards(_regime, error=scrub_secrets(_regime_err) or None,\n                                        attempt=_attempt)\n    _render_tiles(status_bar_tiles_with_trading_day(\n',
         '    #    `EXIT_RETRY_HERE`（對面那句 Z60 起在本頁不成立）；其餘欄位原物件照用。\n    _bar_cards = build_status_bar_cards(_regime, error=scrub_secrets(_regime_err) or None)\n    _render_tiles(status_bar_tiles_with_trading_day(\n'),
        ('            regime=_regime, regime_error=_regime_err,\n            band_zh_color=_band_zh, l4_error=_l4_err,\n            macro_attempt=_attempt))\n\n',
         '            regime=_regime, regime_error=_regime_err,\n            band_zh_color=_band_zh, l4_error=_l4_err))\n\n'),
    ),
    'src/ui/views/page_why.py': (
        ('SOURCE_FAILED_NOW: str = "**最後一次真實抓取失敗了**"\n#: UIA-02（2026-10-18）：L0 記 `ok`，但附加欄 `last_has_content=False`（回 0 列／None）。灰，⛔ 不綠、⛔ 不紅。\nSOURCE_EMPTY_NOW: str = "**有呼叫、沒報錯，但回 0 列／None**"\nSOURCE_EMPTY_WHY: str = (\n    "分不出是上游今天沒資料（非交易日／尚未公布）還是備援全敗 —— "\n    "沒報錯不等於有資料，所以這一盞**不畫綠**；"\n    "本頁也沒有依據說它壞了，所以**不畫紅**。"\n    "判空規則與「今天」頁的更新報告同一支（`shared.fetch_monitor.has_content`：只有 None 與空容器算空，數值 0 算有值）")\nSOURCE_EMPTY_WHERE: str = (\n    "到會用到它的那一頁重按一次更新；"\n    "若在交易日、資料應已公布時仍持續回空，請把這一列回報給維護者")\nEMPTY_REGISTRY_NOW: str = "**這個 session 還沒有任何 fetcher 登錄**"\n',
         'SOURCE_FAILED_NOW: str = "**最後一次真實抓取失敗了**"\nEMPTY_REGISTRY_NOW: str = "**這個 session 還沒有任何 fetcher 登錄**"\n'),
        ('            ⚠️ **不認得一律當紅**，絕不當綠（見 `probe_from_entry`）。\n        empty: UIA-02（2026-10-18）。`ok=True` 但 L0 附加欄 `last_has_content` **明確是 False**\n            （有呼叫、沒報錯，但回 0 列／None）→ 灰（`UI_EMPTY`）。\n            舊紀錄沒有這一欄（或為 None）→ False ＝ 行為與修前相同。\n    """\n',
         '            ⚠️ **不認得一律當紅**，絕不當綠（見 `probe_from_entry`）。\n    """\n'),
        ('    unknown_status: str = ""\n    empty: bool = False\n\n',
         '    unknown_status: str = ""\n\n'),
        ('    if _status == STATUS_OK:\n        # UIA-02：只認**明確的 False**（`is False`）—— 舊紀錄缺欄 / None 照舊畫綠（修前行為）。\n        return SourceProbe(called=True, ok=True,\n                           empty=entry.get("last_has_content") is False, **_common)\n    if _status == STATUS_FAILED:\n',
         '    if _status == STATUS_OK:\n        return SourceProbe(called=True, ok=True, **_common)\n    if _status == STATUS_FAILED:\n'),
        ('    —— 那正是「上游帶下來的 gate 旗標」的定義。\n    """\n    # UIA-02：ok 但回空 → `has_value=False` 且**不帶** `MISS_FETCH_FAILED`（帶了會升紅）\n    #   ⇒ L0 判成 `UI_EMPTY`（灰）。分不出是上游今天沒資料還是備援全敗，⛔ 不綠、⛔ 不紅。\n    _state = classify_ui_state(\n        requested=probe.called,\n',
         '    —— 那正是「上游帶下來的 gate 旗標」的定義。\n    """\n    _state = classify_ui_state(\n        requested=probe.called,\n'),
        ('        error=probe.error or None,\n        has_value=(probe.ok and not probe.empty),\n        reason=("" if (probe.ok and probe.empty) else MISS_FETCH_FAILED))\n    _facts: list[tuple[str, str]] = []\n',
         '        error=probe.error or None,\n        has_value=probe.ok,\n        reason=MISS_FETCH_FAILED)\n    _facts: list[tuple[str, str]] = []\n'),
        ('        _note = Note(now=SOURCE_IDLE_NOW, why=NEVER_RUN_WHY, where=NEVER_RUN_WHERE)\n    elif probe.ok and probe.empty:\n        # UIA-02：時間照樣列出（它是「最後一次真實呼叫」的觀測），但不當結論放大字區。\n        _facts.insert(0, ("最後真實抓取", probe.last_called_at or "（L0 沒有記下時間）"))\n        _note = Note(now=SOURCE_EMPTY_NOW, why=SOURCE_EMPTY_WHY, where=SOURCE_EMPTY_WHERE)\n    elif probe.unknown_status:\n',
         '        _note = Note(now=SOURCE_IDLE_NOW, why=NEVER_RUN_WHY, where=NEVER_RUN_WHERE)\n    elif probe.unknown_status:\n'),
        ('           + "到會用到它的那一頁重按一次更新；若持續失敗請" + V2_EXCERPT_GAP + "回報給維護者")),\n       # UIA-02：ok 但回 0 列／None 的灰卡（三段皆原文摘錄）。\n       _v2_rows_for("why.source.wall", SOURCE_EMPTY_NOW, (\n           None, "分不出是上游今天沒資料（非交易日／尚未公布）還是備援全敗",\n           "到會用到它的那一頁重按一次更新；若" + V2_EXCERPT_GAP + "持續回空，請" + V2_EXCERPT_GAP\n           + "回報給維護者")),\n       _v2_rows_for("why.source.wall", SOURCE_UNKNOWN_NOW_HEAD, (\n',
         '           + "到會用到它的那一頁重按一次更新；若持續失敗請" + V2_EXCERPT_GAP + "回報給維護者")),\n       _v2_rows_for("why.source.wall", SOURCE_UNKNOWN_NOW_HEAD, (\n'),
    ),
}



def _uia_rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def uia_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批（UIA-01/02/07）之前的寫法（無 pair 則原樣）。"""
    rel = _uia_rel(file_path)
    for new, old in UIA_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def test_uia_revert_is_exact_base_source():
    for rel in sorted(UIA_REVERT_PAIRS):
        code = uia_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == UIA_BASE_SHA[rel], rel


import random  # noqa: E402
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from shared import fetch_monitor as FM
from shared.macro_buckets import BUCKET_DANGER_SPECS, MISSING_NO_VALUE, classify_danger
from shared.regime_arbiter import SOURCE_BULL_SCORE, SOURCE_UNLOADED
from shared.ui_state import UI_EMPTY, UI_FAILED, UI_IDLE, UI_LIVE, UI_PARTIAL
from src.ui.tabs import tab_macro_v2 as TV
from src.ui.tabs import tab_today as TT
from src.ui.views import page_today as PT
from src.ui.views import page_why as PW

# ══════════════════════════════════════════════════════════════════
# 共用：造 readiness 側車
# ══════════════════════════════════════════════════════════════════
_SPECS = {s.key: s for s in BUCKET_DANGER_SPECS}
_M = len(BUCKET_DANGER_SPECS)


def _candidates(spec) -> list[float]:
    out = [spec.yellow, spec.red, spec.red + 1e5, spec.red - 1e5]
    out += [x for x in (spec.yellow_lo, spec.red_lo) if x is not None]
    if spec.yellow_lo is not None:
        out.append((spec.yellow + spec.yellow_lo) / 2)
    return out


def _value_for(key: str, band: str) -> float:
    spec = _SPECS[key]
    for v in _candidates(spec):
        if classify_danger(v, spec) == band:
            return v
    raise AssertionError(f"{key} 找不到 {band} 的值")


def _rec(key: str, value: float | None, **extra) -> dict:
    spec = _SPECS[key]
    rec = {"wired": spec.wired, "discriminative": spec.discriminative,
           "state": "ok" if value is not None else "missing", "value": value,
           "reason": None if value is not None else MISSING_NO_VALUE,
           "hit_source": "test" if value is not None else None,
           "candidates": [], "rejected": []}
    rec.update(extra)
    return rec


def _rd(values: dict[str, float | None], **extras: dict) -> dict:
    return {k: _rec(k, values.get(k), **extras.get(k, {})) for k in _SPECS}


_ALL_GREEN = {k: _value_for(k, "green") for k in _SPECS}


def _verdict(rd: dict) -> tuple[str, str]:
    return TV.overall_verdict(TV.bucket_summary(TV.build_rows(rd)))


# 修前（d3425a91）的 bucket_summary／overall_verdict 演算法逐字副本 —— 只用來比對 band 與齊全時的字串。
def _ref_bucket_summary(rows) -> list[dict]:
    rank = {"green": 0, "yellow": 1, "red": 2, "gray": -1}
    out = []
    for bkey in TV._BUCKET_ORDER:
        members = [r for r in rows if r.bucket == bkey]
        if not members:
            continue
        graded = [r for r in members if r.band != "gray"]
        worst = max(graded, key=lambda r: rank[r.band]) if graded else None
        out.append({"name": TV._BUCKET_ZH.get(bkey, bkey),
                    "band": worst.band if worst else "gray"})
    return out


def _ref_overall_verdict(summary) -> tuple[str, str]:
    rank = {"green": 0, "yellow": 1, "red": 2}
    graded = [b for b in summary if b["band"] in rank]
    if not graded:
        return "gray", "尚未載入資料"
    worst = max(graded, key=lambda b: rank[b["band"]])
    n_red = sum(1 for b in graded if b["band"] == "red")
    n_yellow = sum(1 for b in graded if b["band"] == "yellow")
    bits = []
    if n_red:
        bits.append(f"{n_red} 桶紅")
    if n_yellow:
        bits.append(f"{n_yellow} 桶黃")
    detail = "、".join(bits) or "五桶全綠"
    return worst["band"], f"{detail}　·　最差是「{worst['name']}」"


def _ref_verdict(rd: dict) -> tuple[str, str]:
    return _ref_overall_verdict(_ref_bucket_summary(TV.build_rows(rd)))


_BAND_ZH = {"green": ("綠", "#2e7d32"), "yellow": ("黃", "#f9a825"),
            "red": ("紅", "#c62828"), "gray": ("灰", "#9e9e9e")}


def _danger_tile(danger, key="verdict.danger", label="指標危險度（不含多空方向）"):
    return PT._danger_tile(key=key, label=label, danger=danger, danger_error="",
                           danger_requested=True, danger_source=PT.SRC_DANGER,
                           band_zh_color=_BAND_ZH, l4_error="")


# ══════════════════════════════════════════════════════════════════
# UIA-01
# ══════════════════════════════════════════════════════════════════
class TestUIA01Verdict:
    def test_one_of_sixteen_is_not_five_buckets_green(self):
        band, detail = _verdict(_rd({"ndc_signal": 23.0}))
        assert band == "green"                               # 燈色不變
        assert "五桶全綠" not in detail
        assert detail == f"有資料的指標未見黃／紅燈　·　只根據 1／{_M} 項有資料"

    def test_four_of_sixteen_red_discloses_coverage(self):
        vals = {k: _ALL_GREEN[k] for k in ("health", "vix", "us10y")}
        vals["dxy"] = _value_for("dxy", "red")
        band, detail = _verdict(_rd(vals))
        assert band == "red"
        assert detail == f"1 桶紅　·　最差是「中期」　·　只根據 4／{_M} 項有資料"

    def test_full_data_strings_identical_to_pre_fix(self):
        # 字串取自基底 d3425a91 實跑（scratchpad 截取，兩版輸出相同）。
        assert _verdict(_rd(_ALL_GREEN)) == ("green", "五桶全綠　·　最差是「長期」")
        mixed = dict(_ALL_GREEN, margin=_value_for("margin", "red"),
                     vix=_value_for("vix", "yellow"))
        assert _verdict(_rd(mixed)) == ("red", "1 桶紅、1 桶黃　·　最差是「籌碼」")

    def test_all_missing_unchanged(self):
        assert _verdict(_rd({})) == ("gray", "尚未載入資料")

    def test_denominator_is_row_count_not_hardcoded(self):
        rows = TV.build_rows(_rd({"vix": 12.0}))
        assert TV.summary_coverage(TV.bucket_summary(rows)) == (1, len(rows))

    def test_degraded_and_proxy_rows_count_as_having_value(self):
        # margin 恆 degraded（有值）、m1b 代理值（有值、燈不計分）—— ⛔ 不得算成「沒有值」。
        rd = _rd({"margin": 1000.0, "m1b_m2_gap": 5.0},
                 m1b_m2_gap={"is_proxy": True})
        summary = TV.bucket_summary(TV.build_rows(rd))
        assert TV.summary_coverage(summary) == (2, _M)

    def test_hand_built_summary_without_field_keeps_old_behaviour(self):
        summary = [{"name": "長期", "band": "green", "n": 3}]
        assert TV.overall_verdict(summary) == ("green", "五桶全綠　·　最差是「長期」")

    def test_band_never_changes_randomized(self):
        rnd = random.Random(20261018)
        keys = list(_SPECS)
        for _ in range(400):
            vals = {}
            for k in rnd.sample(keys, rnd.randint(0, len(keys))):
                vals[k] = rnd.choice(_candidates(_SPECS[k]))
            rd = _rd(vals)
            new, ref = _verdict(rd), _ref_verdict(rd)
            assert new[0] == ref[0], vals
            n, m = TV.summary_coverage(TV.bucket_summary(TV.build_rows(rd)))
            if n == m or ref == ("gray", "尚未載入資料"):
                assert new == ref, vals
            else:
                assert "五桶全綠" not in new[1]
                assert new[1].endswith(f"只根據 {n}／{m} 項有資料"), new

    def test_coverage_agrees_with_page_today_coverage(self):
        rnd = random.Random(7)
        keys = list(_SPECS)
        for _ in range(50):
            vals = {k: rnd.choice(_candidates(_SPECS[k]))
                    for k in rnd.sample(keys, rnd.randint(0, len(keys)))}
            rd = _rd(vals)
            n, m = TV.summary_coverage(TV.bucket_summary(TV.build_rows(rd)))
            cov = PT.coverage(PT.build_indicator_tiles(
                PT.MacroReadout(requested=True, readiness=rd)))
            # page_today 的分子口徑：運作中 ＋ 已失準（有值）；無資料 / 未接線 / 故障都是沒有值。
            assert (n, m) == (cov.live + cov.stale, cov.total)
            assert m - n == cov.gray + cov.unwired + cov.fault


class TestUIA01Tiles:
    def test_load_danger_carries_completeness(self):
        danger, err, src = PT._load_danger(
            PT.MacroReadout(requested=True, readiness=_rd({"ndc_signal": 23.0})))
        assert err == "" and src == ""
        assert danger[:2] == _verdict(_rd({"ndc_signal": 23.0}))
        assert danger[2] == (1, _M)

    def test_partial_tile_is_partial_not_live(self):
        danger, _, _ = PT._load_danger(
            PT.MacroReadout(requested=True, readiness=_rd({"ndc_signal": 23.0})))
        tile = _danger_tile(danger)
        assert tile.card.state == UI_PARTIAL
        assert tile.card.value == ""
        assert (tile.signal_text, tile.signal_color) == _BAND_ZH["green"]   # 燈號頻道照舊
        facts = dict(tile.facts)
        assert facts[PT.DANGER_DETAIL_FACT_KEY] == danger[1]
        assert f"分母為全部 {_M} 項（含未接線）" in facts[PT.DANGER_BASIS_FACT_KEY]
        assert f"1／{_M}" in tile.card.note.now
        html = PT.v2_card_html(tile)
        assert "<span>運作中</span>" not in html and "bdg-1 " not in html   # 徽章不是 #1 運作中
        assert "五桶全綠" not in html

    def test_full_tile_still_live(self):
        danger, _, _ = PT._load_danger(
            PT.MacroReadout(requested=True, readiness=_rd(_ALL_GREEN)))
        tile = _danger_tile(danger)
        assert tile.card.state == UI_LIVE
        assert tile.card.value == "五桶全綠　·　最差是「長期」"

    def test_two_element_danger_keeps_old_behaviour(self):
        tile = _danger_tile(("green", "x"))
        assert tile.card.state == UI_LIVE and tile.card.value == "x"

    def test_summary_risk_cell_is_partial_too(self):
        danger, _, _ = PT._load_danger(
            PT.MacroReadout(requested=True, readiness=_rd({"vix": 12.0})))
        cards = next(b for b in TT.build_today_blocks() if b.key == "today.summary").cards
        tiles = PT.build_summary_tiles(cards, danger=danger, danger_error="",
                                       danger_requested=True, band_zh_color=_BAND_ZH)
        risk = next(t for t in tiles if t.card.key == PT.SUMMARY_RISK_KEY)
        assert risk.card.state == UI_PARTIAL
        PT.v2_card_html(risk)


# ══════════════════════════════════════════════════════════════════
# UIA-02
# ══════════════════════════════════════════════════════════════════
class TestUIA02HasContent:
    @pytest.mark.parametrize("value,want", [
        (None, False), (pd.DataFrame(), False), ({}, False), ([], False), ("", False),
        (0.0, True), (0, True), (pd.DataFrame({"a": [1]}), True), ({"a": 1}, True),
        (pd.Series([], dtype=float), False), ([None], True),
    ])
    def test_cases(self, value, want):
        assert FM.has_content(value) is want

    def test_service_uses_same_function(self):
        from src.services import macro_refresh_service as RS
        assert RS._has_content is FM.has_content

    def test_mutation_none_as_content_is_caught(self):
        # 突變：若判空把 None 當有資料，「ok 但回 None」就會變綠 —— 這條要能被抓到。
        assert FM.has_content(None) is False


class TestUIA02Monitored:
    def _fetch(self, name, result=None, raises=False):
        @FM.monitored(name, category="t")
        def _f():
            if raises:
                raise RuntimeError("boom")
            return result
        return _f

    def test_records_last_has_content(self):
        f_empty = self._fetch("uia02_empty", pd.DataFrame())
        f_full = self._fetch("uia02_full", pd.DataFrame({"a": [1]}))
        f_zero = self._fetch("uia02_zero", 0.0)
        f_bad = self._fetch("uia02_bad", raises=True)
        reg = FM.get_monitor_registry()
        assert reg["uia02_empty"]["last_has_content"] is None   # 未執行
        f_empty(); f_full(); f_zero()
        with pytest.raises(RuntimeError):
            f_bad()
        reg = FM.get_monitor_registry()
        assert reg["uia02_empty"]["last_status"] == "ok"        # 狀態語意不變
        assert reg["uia02_empty"]["last_has_content"] is False
        assert reg["uia02_full"]["last_has_content"] is True
        assert reg["uia02_zero"]["last_has_content"] is True
        assert reg["uia02_bad"]["last_status"] == "failed"
        assert reg["uia02_bad"]["last_has_content"] is None

    def test_broken_result_does_not_break_fetch(self):
        class _Weird:
            @property
            def empty(self):
                raise RuntimeError("weird")
        w = _Weird()
        assert self._fetch("uia02_weird", w)() is w
        assert FM.get_monitor_registry()["uia02_weird"]["last_has_content"] is None

    def test_end_to_end_empty_source_is_grey(self):
        f = self._fetch("uia02_e2e", None)
        f()
        probe = PW.probe_from_entry("uia02_e2e", FM.get_monitor_registry()["uia02_e2e"])
        card, facts, _ = PW.build_source_card(probe)
        assert card.state == UI_EMPTY


class TestUIA02SourceCard:
    def _card(self, **entry):
        base = {"last_status": "ok", "last_called_at": "2026-10-18 09:00:00",
                "last_rows": 0, "category": "t"}
        base.update(entry)
        return PW.build_source_card(PW.probe_from_entry("f", base))

    def test_ok_but_empty_is_grey_not_live_not_failed(self):
        card, facts, _ = self._card(last_has_content=False)
        assert card.state == UI_EMPTY
        assert card.state not in (UI_LIVE, UI_FAILED)
        assert card.note.now == PW.SOURCE_EMPTY_NOW
        assert "分不出是上游今天沒資料" in card.note.why
        html = PW.v2_card_html(card, facts)
        assert "<span>運作中</span>" not in html and "<span>取得失敗</span>" not in html

    def test_ok_with_data_is_live(self):
        card, _, _ = self._card(last_has_content=True, last_rows=5)
        assert card.state == UI_LIVE

    def test_old_entry_without_field_keeps_old_behaviour(self):
        card, _, _ = self._card()
        assert card.state == UI_LIVE
        card, _, _ = self._card(last_has_content=None)
        assert card.state == UI_LIVE


# ══════════════════════════════════════════════════════════════════
# UIA-07
# ══════════════════════════════════════════════════════════════════
_COLD = {"regime": "unknown", "light": "⬜", "source": SOURCE_UNLOADED, "is_loaded": False,
         "health": None, "exposure_limit_pct": None}
_LIVE = {"regime": "bull", "light": "🟢", "source": SOURCE_BULL_SCORE, "is_loaded": True,
         "traffic_light": "偏多", "health": 70.0}
_FAILED = (TT.MACRO_ATTEMPT_FAILED, "RuntimeError: warroom boom")
_SKIPPED = (TT.MACRO_ATTEMPT_SKIPPED, "大盤評估、旌旗、籌碼三個輸入這一輪都是空的")
_ALLOC_COLD = NS(is_loaded=False, caps=(), drivers=(), posture="", range_text="",
                 cap_text="", conflicts=(), risk_cap_disclosure=None)


def _verdict_tiles(attempt=..., regime=_COLD, regime_error=""):
    kw = {} if attempt is ... else {"macro_attempt": attempt}
    return {t.card.key: t for t in PT.build_verdict_tiles(
        alloc=_ALLOC_COLD, alloc_error="", danger=None, danger_error="",
        danger_requested=False, regime=regime, regime_error=regime_error, **kw)}


class TestUIA07Classify:
    @pytest.mark.parametrize("state,error", [
        (_COLD, None), (_LIVE, None), (None, None), (_COLD, "RuntimeError('x')"),
    ])
    def test_attempt_none_identical(self, state, error):
        assert (TT.classify_macro_contract(state, error=error, attempt=None)
                == TT.classify_macro_contract(state, error=error))

    def test_failed_attempt_is_red(self):
        assert TT.classify_macro_contract(_COLD, attempt=_FAILED) == UI_FAILED

    def test_skipped_and_ok_attempt_are_grey_empty(self):
        assert TT.classify_macro_contract(_COLD, attempt=_SKIPPED) == UI_EMPTY
        assert TT.classify_macro_contract(
            _COLD, attempt=(TT.MACRO_ATTEMPT_OK, "健康分缺")) == UI_EMPTY

    def test_valid_summary_wins(self):
        assert TT.classify_macro_contract(_LIVE, attempt=_FAILED) == UI_LIVE

    def test_contract_error_wins(self):
        assert TT.classify_macro_contract(_COLD, error="E", attempt=_SKIPPED) == UI_FAILED
        assert TT.macro_attempt_failed_reason(_COLD, error="E", attempt=_FAILED) is None

    def test_unknown_status_fails_loud(self):
        with pytest.raises(ValueError):
            TT.classify_macro_contract(_COLD, attempt=("weird", ""))


class TestUIA07Tiles:
    def test_failed_attempt_exposure_card_is_red_with_reason(self):
        tiles = _verdict_tiles(_FAILED)
        exp = tiles["verdict.exposure"]
        assert exp.card.state == UI_FAILED
        assert "上一次更新時紅綠燈整理失敗" in exp.card.note.why
        assert "warroom boom" in exp.card.note.why
        for t in tiles.values():
            if t.card.note is not None:
                assert "還沒有人叫過" not in t.card.note.why
        assert tiles["verdict.regime"].card.state == UI_FAILED
        assert "warroom boom" in tiles["verdict.regime"].card.note.why
        for t in tiles.values():
            PT.v2_card_html(t)

    def test_skipped_attempt_is_grey_empty_with_reason(self):
        exp = _verdict_tiles(_SKIPPED)["verdict.exposure"]
        assert exp.card.state == UI_EMPTY
        assert "三個輸入這一輪都是空的" in exp.card.note.why
        assert "還沒有人叫過" not in exp.card.note.why

    def test_no_attempt_identical_and_idle(self):
        assert _verdict_tiles(None) == _verdict_tiles()
        assert _verdict_tiles(None)["verdict.exposure"].card.state == UI_IDLE

    def test_valid_summary_wins_over_failed_attempt(self):
        with_att = _verdict_tiles(_FAILED, regime=_LIVE)
        assert with_att == _verdict_tiles(regime=_LIVE)
        assert with_att["verdict.regime"].card.state == UI_LIVE

    def test_status_bar_and_blocks(self):
        bar = next(c for c in TT.build_status_bar_cards(_COLD, attempt=_FAILED)
                   if c.key == "statusbar.macro")
        assert bar.state == UI_FAILED
        assert "上一次更新時紅綠燈整理失敗" in bar.note.why
        assert "讀 L3 canonical 契約時拋出例外" not in bar.note.why   # 出處不講錯
        reg = next(c for b in TT.build_today_blocks(macro_state=_COLD, macro_attempt=_FAILED)
                   for c in b.cards if c.key == "summary.regime")
        assert reg.state == UI_FAILED
        assert TT.build_today_blocks(macro_state=_COLD) == TT.build_today_blocks(
            macro_state=_COLD, macro_attempt=None)

    def test_warroom_attempt_from_report(self):
        from src.services.macro_refresh_service import (
            STEP_WARROOM, MacroRefreshReport, StepResult)
        mk = lambda step: MacroRefreshReport(mode="warm", started_at="t", elapsed_s=0.0,  # noqa: E731
                                             steps=(step,))
        assert PT.warroom_attempt(None) is None
        assert PT.warroom_attempt(mk(StepResult(STEP_WARROOM, False, "boom"))) == (
            TT.MACRO_ATTEMPT_FAILED, "boom")
        assert PT.warroom_attempt(mk(StepResult(STEP_WARROOM, True, "空", skipped=True))) == (
            TT.MACRO_ATTEMPT_SKIPPED, "空")
        assert PT.warroom_attempt(mk(StepResult(STEP_WARROOM, True, "寫入"))) == (
            TT.MACRO_ATTEMPT_OK, "寫入")
        assert PT.warroom_attempt(mk(StepResult("other", False, "x"))) is None
        assert PT.warroom_attempt(NS()) is None                      # 舊格式報告不炸
