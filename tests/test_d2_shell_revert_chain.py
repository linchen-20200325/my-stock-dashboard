"""tests/test_d2_shell_revert_chain.py — D2 導覽殼（DEC-089 G1＝C／DEC-090）對 `src/ui/views/page_hold.py` 的還原鏈新頭節。

═══ 為什麼需要 ═══════════════════════════════════════════════════════════
D2 為了讓 `ia_nav.where_to_find` 多帶方向名（DEC-090 ⑦）後，page_hold 的三句**卡面短句摘錄**仍 ≤ `FACT_VALUE_MAX_CHARS`（46），
動了該檔 4 處（見 `D2_REVERT_PAIRS`）。舊鏈（`sheet_safety_revert_for` → `me_p1_revert_for` → … → `dec074_revert_for` …）
用「新寫法 → 舊寫法」錨點把 page_hold 還原成各自的基底 sha；D2 的改動落在它們的錨點之內 ⇒ 需在鏈頭**往前接一節**，
先把 D2 換回（比照 `me_p1_revert_for` 接 `sheet_safety_revert_for` 的作法；⛔ 不動任何舊表與舊基底 sha）。

基底 ＝ D2 開工前的 `ad0a3c2`（main）。pair 由 `git diff ad0a3c2` 以 `difflib` 分組產生，並於產生時驗證
「套用後逐字等於基底、且每個新寫法在現行檔恰出現 1 次」。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

D2_BASE_SHA = {'src/ui/views/page_hold.py': 'c6d3159ada1801d8192e81635ca1238e718813a807d099e558d5fbd3f0f2d511'}

D2_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'src/ui/views/page_hold.py': (('    GOOGLE_NOT_ASKED_NOW: (\n'
  '        "這一輪沒有讀 Google Sheet",\n'
  '        "本頁因此真的沒有發那一次網路呼叫，不是發了失敗",\n'
  '        # 📌 D2 導覽殼（DEC-090 ⑦，有意識的修改，⛔ 不是漏改）：`SETUP_WHERE` 多帶方向名「🛡️ 持股 › 」後這句 47 字，\n'
  '        #   超過卡面短句上限 `FACT_VALUE_MAX_CHARS`（46）會被契約層截斷 ⇒ 摘錄只拿掉開頭那個「到」字\n'
  '        #   （摘錄本來就是全文的子字串，起點可從句中開始；全文 `SCOPE_NOT_ASKED_WHERE` 與語意一字不動）。\n'
  '        #   原：~~"到" + SETUP_WHERE + …~~\n'
  '        SETUP_WHERE + "把選項改成「加讀 Google Sheet" + V2_EXCERPT_GAP + "」"),\n'
  '    NOT_BOUND_NOW: ("你還沒有綁定持股 Sheet",\n'
  '                    "這是一個有效的結果" + V2_EXCERPT_GAP + "沒有綁定就沒有清單可讀",\n'
  '                    # 👤 我的 P1：~~… + "現行入口在側欄「🔐 Google 帳號」"~~\n',
  '    GOOGLE_NOT_ASKED_NOW: (\n'
  '        "這一輪沒有讀 Google Sheet",\n'
  '        "本頁因此真的沒有發那一次網路呼叫，不是發了失敗",\n'
  '        "到" + SETUP_WHERE + "把選項改成「加讀 Google Sheet" + V2_EXCERPT_GAP + "」"),\n'
  '    NOT_BOUND_NOW: ("你還沒有綁定持股 Sheet",\n'
  '                    "這是一個有效的結果" + V2_EXCERPT_GAP + "沒有綁定就沒有清單可讀",\n'
  '                    # 👤 我的 P1：~~… + "現行入口在側欄「🔐 Google 帳號」"~~\n'),
 ('           "若你預期應該要有：先看上面 ① 的「訊號可信度」")),\n'
  '       _v2_rows_for("hold.macro_stage", MACRO_FAILED_NOW, (\n'
  '           None, _v2_raised(SRC_MACRO),\n'
  '           _V2_NO_EXIT_REPORT + V2_EXCERPT_GAP + "本身的狀態在" + ia_nav.where_to_find(ia_nav.PAGE_TODAY))),\n'
  '       # ↑ D2（DEC-090 ⑦，有意識的修改，⛔ 不是漏改）：指路句改走 SSOT（多帶方向名「📊 大盤 › 」）後原摘錄\n'
  '       #   「…總經本身的狀態在「📊 大盤 › 🚦 今天」」47 字 > `FACT_VALUE_MAX_CHARS`（46）會被截斷 ⇒ 摘錄起點後移\n'
  '       #   兩個字（「總經」）；摘錄是全文的子字串，全文與語意一字不動。原：~~"總經本身的狀態在「🚦 今天」"~~\n'
  '       # 📌 QA-6 MUST-1（2026-10-23，PR #910，有意識的修改，⛔ 不是漏刪；決策者 AI 總管）：同一個 `MACRO_EMPTY_NOW`\n'
  '       #   還有兩支分支（缺真實廣度 `_breadth_empty_why()`／`_BREADTH_EMPTY_WHERE`、尚未載入＋代理廣度不計分\n'
  '       #   `NOT_LOADED_PENDING_BREADTH_*_HOLD`），原文與下面第一個候選不同 ⇒ 修前只有一個候選 ⇒ `KeyError` ⇒ 紅卡。\n',
  '           "若你預期應該要有：先看上面 ① 的「訊號可信度」")),\n'
  '       _v2_rows_for("hold.macro_stage", MACRO_FAILED_NOW, (\n'
  '           None, _v2_raised(SRC_MACRO),\n'
  '           _V2_NO_EXIT_REPORT + V2_EXCERPT_GAP + "總經本身的狀態在「🚦 今天」")),\n'
  '       # 📌 QA-6 MUST-1（2026-10-23，PR #910，有意識的修改，⛔ 不是漏刪；決策者 AI 總管）：同一個 `MACRO_EMPTY_NOW`\n'
  '       #   還有兩支分支（缺真實廣度 `_breadth_empty_why()`／`_BREADTH_EMPTY_WHERE`、尚未載入＋代理廣度不計分\n'
  '       #   `NOT_LOADED_PENDING_BREADTH_*_HOLD`），原文與下面第一個候選不同 ⇒ 修前只有一個候選 ⇒ `KeyError` ⇒ 紅卡。\n'),
 ('       _v2_rows_for("hold.macro_stage", MACRO_EMPTY_NOW, (\n'
  '           None, ("本站不以「中性」代替未評估：多空是一個結論，缺值不是",\n'
  '                  _V2_BREADTH_EMPTY_WHY, _V2_NOT_LOADED_PENDING_BREADTH_WHY),\n'
  '           ("到" + ia_nav.where_to_find(ia_nav.PAGE_TODAY) + "更新總經之後，回到本頁" + _V2_PRESS_RUN,\n'
  '            _V2_BREADTH_EMPTY_WHERE, _V2_NOT_LOADED_PENDING_BREADTH_WHERE)))]\n'
  '    # ── ⑤ 80/20 偏離 ＋ 衛星停利 ＋ 建議持股水位（核心／衛星與 80/20 同一則 Note）──\n'
  '    # 📌 Q2-r3（2026-09-27，有意識的刪除，⛔ 不是漏刪）：`NO_PRICE_WHY` 改為客戶逐字句（45 字）後，\n',
  '       _v2_rows_for("hold.macro_stage", MACRO_EMPTY_NOW, (\n'
  '           None, ("本站不以「中性」代替未評估：多空是一個結論，缺值不是",\n'
  '                  _V2_BREADTH_EMPTY_WHY, _V2_NOT_LOADED_PENDING_BREADTH_WHY),\n'
  '           ("到「🚦 今天」更新總經之後，回到本頁" + _V2_PRESS_RUN,\n'
  '            _V2_BREADTH_EMPTY_WHERE, _V2_NOT_LOADED_PENDING_BREADTH_WHERE)))]\n'
  '    # ── ⑤ 80/20 偏離 ＋ 衛星停利 ＋ 建議持股水位（核心／衛星與 80/20 同一則 Note）──\n'
  '    # 📌 Q2-r3（2026-09-27，有意識的刪除，⛔ 不是漏刪）：`NO_PRICE_WHY` 改為客戶逐字句（45 字）後，\n'),
 ('       # 📌 QA-6 MUST-1（同上，有意識的修改，⛔ 不是漏刪）：缺真實廣度那一支原文不同 ⇒ 補一組候選；既有候選一字未改。\n'
  '       _v2_rows_for("hold.position_cap", CAP_EMPTY_NOW, (\n'
  '           None, ("填一個看起來合理的區間，等於替你做了一個沒有依據的決定", _V2_BREADTH_EMPTY_WHY),\n'
  '           ("到" + ia_nav.where_to_find(ia_nav.PAGE_TODAY) + "更新總經之後，回到本頁" + _V2_PRESS_RUN, _V2_BREADTH_EMPTY_WHERE))),\n'
  '       # 批 Z65 QA：取不到有效系統風險上限（客戶 Q-z34～36 規則）。摘錄自原文（K1）。\n'
  '       _v2_rows_for("hold.position_cap", RISK_CAP_UNAVAILABLE_NOW, (\n'
  '           None, "目前沒有可用的系統風險上限" + V2_EXCERPT_GAP + "系統不會在缺上限的情況下給持股數字",\n',
  '       # 📌 QA-6 MUST-1（同上，有意識的修改，⛔ 不是漏刪）：缺真實廣度那一支原文不同 ⇒ 補一組候選；既有候選一字未改。\n'
  '       _v2_rows_for("hold.position_cap", CAP_EMPTY_NOW, (\n'
  '           None, ("填一個看起來合理的區間，等於替你做了一個沒有依據的決定", _V2_BREADTH_EMPTY_WHY),\n'
  '           ("到「🚦 今天」更新總經之後，回到本頁" + _V2_PRESS_RUN, _V2_BREADTH_EMPTY_WHERE))),\n'
  '       # 批 Z65 QA：取不到有效系統風險上限（客戶 Q-z34～36 規則）。摘錄自原文（K1）。\n'
  '       _v2_rows_for("hold.position_cap", RISK_CAP_UNAVAILABLE_NOW, (\n'
  '           None, "目前沒有可用的系統風險上限" + V2_EXCERPT_GAP + "系統不會在缺上限的情況下給持股數字",\n'))}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def d2_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 D2 導覽殼之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = D2_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} D2 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_d2_revert_is_exact_base_source():
    for rel in sorted(D2_REVERT_PAIRS):
        code = d2_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == D2_BASE_SHA[rel], rel


def test_d2_revert_is_idempotent():
    for rel in sorted(D2_REVERT_PAIRS):
        once = d2_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert d2_revert_for(rel, once) == once, rel


def test_chain_head_calls_d2_first():
    """原鏈頭 `sheet_safety_revert_for` 必須先呼叫本節（否則舊批次的基底 sha 守衛看到的是 D2 的新寫法）。"""
    import inspect

    from tests.test_sheet_safety_revert_chain import sheet_safety_revert_for
    src = inspect.getsource(sheet_safety_revert_for)
    assert src.index("d2_revert_for(rel, code)") < src.index("me_p1_revert_for(rel, code)")
