"""tests/test_d2_staleness_revert_chain.py — D2(未來日期 as_of 守衛)對 `macro_cache_reader.py` 的還原鏈新頭節。

═══ 為什麼需要 ═══════════════════════════════════════════════════════════
D2 在 `compute_cache_staleness` 加了一段守衛(as_of 晚於 today ⇒ is_stale=True、「無法判定」)。
`src/data/macro/macro_cache_reader.py` 被舊鏈(Z40／Z63／C1…)以「新寫法 → 舊寫法」錨點還原成各自的基底 sha256;
D2 的新增行落在它們的比對範圍之內 ⇒ 需在鏈頭**往前接一節**,先把 D2 換回
(比照 `p4_revert_for` 接在 `uim_revert_for` 開頭的作法;⛔ 不動任何舊表與舊基底 sha、不放寬任何斷言)。

基底 ＝ D2 開工前的 `0205420`(main);`git show 0205420:<檔> | sha256sum` 實算後寫死,測試不依賴 git。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_MCR_REL = "src/data/macro/macro_cache_reader.py"

D2STALE_BASE_SHA = {
    _MCR_REL: "90c6042f45c0e01cd9ff6381a5dbb8c4ecb09f9d5f2c07d353312f328a90a72e",
}

D2STALE_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _MCR_REL: ((
        '    # D2:資料觀測日晚於 today(未來日期)→ 無法判定新鮮度。\n'
        '    # 可能是系統時鐘錯、上游日期壞或資料被污染;絕不能落到下方「age ≤ 門檻 → fresh」\n'
        '    # (負的 age_days 永遠 ≤ 門檻,月頻 periods_behind 也 ≤ 0)而被當成最新鮮。\n'
        '    # §1 判不出來 → 視為過期;as_of / age_days(負值)照實保留供診斷,日頻與月頻同一出口。\n'
        '    if _as_of > _today:\n'
        '        out["reason"] = (f"{dataset} 資料日 {_as_of} 晚於今日 {_today},無法判定新鮮度"\n'
        '                         f"(時鐘或上游日期異常)→ 視為過期(§1 不假設新鮮)")\n'
        '        return out\n'
        '\n',
        '',
    ),),
}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def d2stale_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`(或 repo 相對路徑)與原始碼,換回 D2 守衛之前的寫法(無 pair 則原樣;只套一次)。"""
    # 📌 D3 B2 空抓取三態消費端一致性(DEC-148,2026-11-08;有意識的接鏈,⛔ 不是漏改):B2 也改了 `macro_cache_reader.py`
    #   (在 D2 守衛之後)⇒ 本節自己的基底 sha 守衛要先把較新的 B2 換回(比照 `c1_revert_for` 開頭先呼叫 `c2a_revert_for`;
    #   只套一次、冪等;⛔ 不動本表與 D2STALE_BASE_SHA、不放寬任何斷言)。
    from tests.test_b2_consumer_revert_chain import b2_revert_for
    code = b2_revert_for(file_path, code)
    rel = _rel(file_path)
    pairs = D2STALE_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} D2 守衛還原組錨點漂移(各組出現次數 {counts};應全 1 或全 0)—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_d2stale_revert_is_exact_base_source():
    assert set(D2STALE_REVERT_PAIRS) == set(D2STALE_BASE_SHA)
    for rel in sorted(D2STALE_REVERT_PAIRS):
        code = d2stale_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == D2STALE_BASE_SHA[rel], rel


def test_d2stale_revert_is_idempotent():
    for rel in sorted(D2STALE_REVERT_PAIRS):
        once = d2stale_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert d2stale_revert_for(rel, once) == once, rel


def test_d2stale_anchor_present_once_in_current_file():
    """守衛真的在現行檔(恰 1 次);還原後 0 次 —— 防止還原組變成空轉。"""
    for rel, pairs in D2STALE_REVERT_PAIRS.items():
        cur = (REPO / rel).read_text(encoding="utf-8")
        base = d2stale_revert_for(rel, cur)
        for new, _old in pairs:
            assert cur.count(new) == 1 and base.count(new) == 0, (rel, new[:60])


def test_chain_head_calls_d2stale_first():
    """原鏈頭 `p4_revert_for` 必須先呼叫本節(否則舊批次的基底 sha 守衛看到的是 D2 的新寫法)。"""
    import inspect

    from tests.test_p4_revert_chain import p4_revert_for
    src = inspect.getsource(p4_revert_for)
    assert src.index("d2stale_revert_for(file_path, code)") < src.index("P4_REVERT_PAIRS.get(rel")
