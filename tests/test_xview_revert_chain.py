"""tests/test_xview_revert_chain.py — xview 安全小修（V1）對 `dividend_station_service.py` 的還原鏈新頭節。

為什麼需要：xview V1 在 `build_summary_prompt` 加了「有效判斷檔數 0 → 不送續抱引導句」的條件；
`dividend_station_service.py` 被舊鏈（`sheet_safety_revert_for` → … → `dec074_revert_for` 的
`DEC074_BASE_SHA`）以基底 sha 守衛 ⇒ 在鏈頭**往前接一節**，先把 xview 改動換回
（比照 `nav1_revert_for` 接 `sheet_safety_revert_for` 的作法；⛔ 不動任何舊表與舊基底 sha）。

基底 ＝ `739fa361`（xview 安全小修開工前的 main）。pair 於產生時驗證「套用後逐字等於基底、
且每個新寫法在現行檔恰出現 1 次」。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

XVIEW_BASE_SHA = {'src/services/dividend_station_service.py': 'b08853b73235da193e66b0465b143d740549da398261d9c91ded5d256980d750'}

XVIEW_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    'src/services/dividend_station_service.py': (('from __future__ import annotations\n\nimport math\nimport numbers\nfrom typing import Callable\n',
  'from __future__ import annotations\n\nfrom typing import Callable\n'),
 ('    # xview V1：有效判斷檔數 0（每檔抓取全失敗／total 缺或非數）→ 也**不送**「續抱」那句 ——\n'
  '    # 比照 LINE 正文 `format_holdings_message` 既有 `total<=0` 防線（稽核🔴A）：零資料不給安心結論。\n'
  '    # 只看 total；部分失敗／燈全 ⚪／無現價**不在**此列（客戶 Z51/Z52 範圍，既有測試釘住）。\n'
  '    # QA 回修：total 須為**有限值且 ≥1** 才算有判斷（inf／NaN／0.5 → 不可判斷；與 LINE 正文 `int()` 後 `<=0` 同向）。\n'
  '    _tot = digest.get("total")\n'
  '    _no_judged = not (isinstance(_tot, numbers.Real) and not isinstance(_tot, bool)\n'
  '                      and math.isfinite(_tot) and _tot >= 1)\n'
  '    _base = (\n'
  '        "你是台股『存股戰情室』的推播助理。根據以下今日持股健檢結果,用繁體中文寫 3~6 句的推播摘要,"\n'
  '        "聚焦『今天要不要動作』。只能引用下列數據,嚴禁自行杜撰任何代號、數字或未列出的結論;"\n'
  '        + ("" if (_inv or _no_judged) else "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。") + "\\n"\n',
  '    _base = (\n'
  '        "你是台股『存股戰情室』的推播助理。根據以下今日持股健檢結果,用繁體中文寫 3~6 句的推播摘要,"\n'
  '        "聚焦『今天要不要動作』。只能引用下列數據,嚴禁自行杜撰任何代號、數字或未列出的結論;"\n'
  '        + ("" if _inv else "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。") + "\\n"\n')),
}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def xview_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 xview 安全小修之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = XVIEW_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} xview 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_xview_revert_is_exact_base_source():
    for rel in sorted(XVIEW_REVERT_PAIRS):
        code = xview_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == XVIEW_BASE_SHA[rel], rel


def test_xview_revert_is_idempotent():
    for rel in sorted(XVIEW_REVERT_PAIRS):
        once = xview_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert xview_revert_for(rel, once) == once, rel


def test_chain_head_calls_xview_before_nav1():
    """原鏈頭 `sheet_safety_revert_for` 必須先呼叫本節（否則舊批次的基底 sha 守衛看到的是還沒還原的檔）。"""
    import inspect

    from tests.test_sheet_safety_revert_chain import sheet_safety_revert_for
    src = inspect.getsource(sheet_safety_revert_for)
    assert src.index("xview_revert_for(rel, code)") < src.index("nav1_revert_for(rel, code)")
