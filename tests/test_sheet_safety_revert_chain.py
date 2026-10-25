"""Sheet Safety 批 QA 回修（N-2，2026-10-25）—— 舊批次「還原鏈」的最新一節。

本 repo 慣例（見 `tests/test_dec074_revert_chain.py` 檔頭）：每個批次登記自己的 `(新寫法, 舊寫法)` 還原組，
舊批次的回歸測試先把「更新的批次」換回去、再換回自己那一批，最後逐位比對各自的基底 sha256。
本批（QA 回修 N-2）改了 `src/ui/views/page_hold.py`（表頭不符時「去哪補」改成「改第一列」）—— 該檔被
c21／z66b／uia／vn1b2／dec074…等舊鏈管 ⇒ 在鏈頭往前接一節：`sheet_safety_revert_for` 把本批改動換回基底
（`b8d6fc40`，本批 N-2 開工前；page_hold 自 main `7739a6aa` 起未動）。由 `tests/test_c2a_risk_cap_shadow.py::
c2a_revert_for`（原鏈頭）在最前面呼叫。

還原組由 difflib 對 `git show b8d6fc40:<檔>` 與工作樹逐 hunk 產生（最小唯一上下文），
`test_sheet_safety_revert_is_exact_base_source` 守：還原後逐位等於基底 sha256（寫死，測試不依賴 git）。
⚠️ 只套一次（idempotent，判定同 dec074／c1／c2a）：各組 `新寫法` 全 1 次 ⇒ 換回；全 0 次 ⇒ 已換回、原樣返回；
其餘 ⇒ AssertionError（錨點漂移，必須重產還原組）。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SHEET_SAFETY_BASE_SHA = {
    "src/ui/views/page_hold.py": "221d2702e935a747d4f62d0856472d42ba5452c4dc31ac63775f35cc3791e3c5",
}

SHEET_SAFETY_REVERT_PAIRS = {'src/ui/views/page_hold.py': (('    沒登入判斷    L3 '
                                '`services.portfolio_binding_service.is_login_required_error`  ← '
                                '1.0-B2（純判斷式，唯讀）\n'
                                '    表頭不符判斷  L3 `services.portfolio_binding_service.sheet_read_issue` / '
                                '`portfolio_worksheet_headers`  ← Sheet Safety QA N-2（純判斷式 / 常數，唯讀）\n'
                                '    VIX（單獨）   L3 `services.dividend_station_service.fetch_vix`\n',
                                '    沒登入判斷    L3 '
                                '`services.portfolio_binding_service.is_login_required_error`  ← '
                                '1.0-B2（純判斷式，唯讀）\n'
                                '    VIX（單獨）   L3 `services.dividend_station_service.fetch_vix`\n'),
                               ('    #: 1.0-B2:登入已逾時(L3 `BindingState.login_expired`)→ '
                                '「未綁」灰卡改寫成「登入已逾時」(仍是灰)。\n'
                                '    login_expired: bool = False\n'
                                '    #: Sheet Safety 批 QA 回修 N-2(只加不改):L3 `BindingState.sheet_issue` 原樣透傳 —— '
                                '讀組合清單那一步\n'
                                '    #: 為什麼沒拿到本數(例 `schema_mismatch`)。只用來挑「怎麼辦」那一句,不參與狀態判定。\n'
                                '    sheet_issue: str = ""\n'
                                '\n'
                                '    @property\n',
                                '    #: 1.0-B2:登入已逾時(L3 `BindingState.login_expired`)→ '
                                '「未綁」灰卡改寫成「登入已逾時」(仍是灰)。\n'
                                '    login_expired: bool = False\n'
                                '\n'
                                '    @property\n'),
                               ('        portfolio_count=_count,\n'
                                '        count_missing_reason=_reason,\n'
                                '        sheet_issue=str(getattr(_s, "sheet_issue", "") or ""))\n'
                                '\n',
                                '        portfolio_count=_count,\n        count_missing_reason=_reason)\n\n'),
                               ('    error: str = ""\n'
                                '    #: Sheet Safety 批 QA 回修 N-2(只加不改):`error` 的分類(L3 `sheet_read_issue`,例 '
                                '`schema_mismatch`)。\n'
                                '    #: 只用來挑「怎麼辦」那一句,不參與狀態判定。\n'
                                '    sheet_issue: str = ""\n'
                                '    #: 1.0-B2:登入已逾時 → `bound=False` ＋ 空清單,卡片畫灰色「登入已逾時」(⛔ 不是紅色讀取失敗)。\n',
                                '    error: str = ""\n'
                                '    #: 1.0-B2:登入已逾時 → `bound=False` ＋ 空清單,卡片畫灰色「登入已逾時」(⛔ 不是紅色讀取失敗)。\n'),
                               ('        print(f"[views/page_hold] 持股清單讀取失敗 → '
                                '轉紅態：{scrub_secrets(repr(_e))}")\n'
                                '        from src.services.portfolio_binding_service import '
                                'sheet_read_issue\n'
                                '        return HoldingsReadout(requested=True, submitted=req.submitted,\n',
                                '        print(f"[views/page_hold] 持股清單讀取失敗 → '
                                '轉紅態：{scrub_secrets(repr(_e))}")\n'
                                '        return HoldingsReadout(requested=True, submitted=req.submitted,\n'),
                               ('        return HoldingsReadout(requested=True, submitted=req.submitted,\n'
                                '                               error=repr(_e), '
                                'sheet_issue=sheet_read_issue(_e))\n'
                                '    return HoldingsReadout(\n',
                                '        return HoldingsReadout(requested=True, submitted=req.submitted,\n'
                                '                               error=repr(_e))\n'
                                '    return HoldingsReadout(\n'),
                               ('PREVIEW_FAILED_NOW: str = "**持股清單讀不出來**"\n'
                                '#: Sheet Safety 批 QA 回修 N-2:「組合分頁第一列欄名不對」的兩則 `now`(紅;去哪補 ＝ 改第一列,\n'
                                '#: ⛔ 不叫人重新登入 / 查網路 —— 登入一百次也一樣)。\n'
                                'COUNT_SCHEMA_MISMATCH_NOW: str = "**讀得到這本 Sheet，但組合分頁的第一列欄名不對**"\n'
                                'PREVIEW_SCHEMA_MISMATCH_NOW: str = "**持股清單讀不出來：組合分頁的第一列欄名不對**"\n'
                                'SCHEMA_MISMATCH_WHY: str = (\n'
                                '    "「portfolios」分頁第一列（欄名）和系統預期的不一樣 —— 為了不改動你的資料，"\n'
                                '    "系統**不會自動修正**，這一輪也不讀任何一列")\n'
                                '#: ⑥ 三格「有值但失準」的 `now`。**原本是 `_degraded_note()` 裡的 f-string，字一字未改**；\n',
                                'PREVIEW_FAILED_NOW: str = "**持股清單讀不出來**"\n'
                                '#: ⑥ 三格「有值但失準」的 `now`。**原本是 `_degraded_note()` 裡的 f-string，字一字未改**；\n'),
                               ('\n'
                                'def _is_schema_mismatch(issue: str) -> bool:\n'
                                '    """L3 分類代碼是不是「表頭不符」(代碼 SSOT 在 L3 / L1,本頁不手抄字面值)。"""\n'
                                '    from src.services.portfolio_binding_service import '
                                'SHEET_ISSUE_SCHEMA_MISMATCH\n'
                                '    return bool(issue) and issue == SHEET_ISSUE_SCHEMA_MISMATCH\n'
                                '\n'
                                '\n'
                                'def _schema_mismatch_where() -> str:\n'
                                '    """表頭不符時的「去哪補」:列出 `portfolios` 分頁應有的第一列(取自 L3 → L1 SSOT,⛔ 不手抄)。"""\n'
                                '    from src.services.portfolio_binding_service import '
                                'portfolio_worksheet_headers\n'
                                '    return ("打開那本 Sheet 的「portfolios」分頁，把第一列從 A 欄起依序改成："\n'
                                '            + "、".join(portfolio_worksheet_headers())\n'
                                '            + "（右邊可以自己加欄）；系統不會替你改。改好後回本頁" + '
                                'press(ACTION_RUN_WARROOM_LABEL))\n'
                                '\n'
                                '\n'
                                'def build_portfolio_count_card(binding: BindingReadout) -> _Built:\n',
                                '\ndef build_portfolio_count_card(binding: BindingReadout) -> _Built:\n'),
                               ('            where="先完成上一張卡說的綁定，這一格會自己有東西")\n'
                                '    elif _state == UI_FAILED and not binding.error and '
                                '_is_schema_mismatch(binding.sheet_issue):\n'
                                '        # QA N-2:表頭不符 ⇒ 去哪補是「改第一列」,⛔ 不是重新登入 / 確認分享(那是錯的指引)。\n'
                                '        _note = Note(now=COUNT_SCHEMA_MISMATCH_NOW, '
                                'why=SCHEMA_MISMATCH_WHY,\n'
                                '                     where=_schema_mismatch_where())\n'
                                '    elif _state == UI_FAILED:\n',
                                '            where="先完成上一張卡說的綁定，這一格會自己有東西")\n'
                                '    elif _state == UI_FAILED:\n'),
                               ('        _note = _idle_note(holdings.scope_idle)\n'
                                '    elif _state == UI_FAILED and '
                                '_is_schema_mismatch(holdings.sheet_issue):\n'
                                '        # QA N-2:表頭不符 ⇒ 去哪補是「改第一列」,⛔ 不是查網路 / 授權(那是錯的指引)。\n'
                                '        _note = Note(now=PREVIEW_SCHEMA_MISMATCH_NOW,\n'
                                '                     why=_error_why(SRC_HOLDINGS, holdings.error),\n'
                                '                     where=_schema_mismatch_where())\n'
                                '    elif _state == UI_FAILED:\n',
                                '        _note = _idle_note(holdings.scope_idle)\n'
                                '    elif _state == UI_FAILED:\n'),
                               ('       _v2_rows_for("hold.setup.preview", PREVIEW_FAILED_NOW, (\n'
                                '           None, _v2_raised(SRC_HOLDINGS), _V2_CHECK_NET)),\n'
                                '       # Sheet Safety 批 QA 回修 N-2:表頭不符的兩則(去哪補 ＝ 改第一列)。\n'
                                '       _v2_rows_for("hold.portfolio_count", COUNT_SCHEMA_MISMATCH_NOW, (\n'
                                '           None, "第一列（欄名）和系統預期的不一樣",\n'
                                '           "「portfolios」分頁，把第一列從 A 欄起依序改成" + V2_EXCERPT_GAP + "改好後回本頁")),\n'
                                '       _v2_rows_for("hold.setup.preview", PREVIEW_SCHEMA_MISMATCH_NOW, (\n'
                                '           None, _v2_raised(SRC_HOLDINGS),\n'
                                '           "「portfolios」分頁，把第一列從 A 欄起依序改成" + V2_EXCERPT_GAP + "改好後回本頁"))]\n'
                                '    + [_v2_rows_for(_k, _now, (\n',
                                '       _v2_rows_for("hold.setup.preview", PREVIEW_FAILED_NOW, (\n'
                                '           None, _v2_raised(SRC_HOLDINGS), _V2_CHECK_NET))]\n'
                                '    + [_v2_rows_for(_k, _now, (\n'))}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def sheet_safety_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = SHEET_SAFETY_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} Sheet Safety 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_sheet_safety_revert_is_exact_base_source():
    for rel in sorted(SHEET_SAFETY_REVERT_PAIRS):
        code = sheet_safety_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == SHEET_SAFETY_BASE_SHA[rel], rel


def test_sheet_safety_revert_is_idempotent():
    for rel in sorted(SHEET_SAFETY_REVERT_PAIRS):
        once = sheet_safety_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert sheet_safety_revert_for(rel, once) == once, rel
