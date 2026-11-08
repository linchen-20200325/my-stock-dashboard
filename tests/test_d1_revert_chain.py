"""tests/test_d1_revert_chain.py — D1(板塊資金潮汐新鮮度改取可信觀測日,客戶 2026-11-08 核准 DEC-148)對
`src/ui/views/page_find.py` 的還原鏈新頭節。

═══ 為什麼需要 ═══════════════════════════════════════════════════════════
D1 讓 `SectorFlowReadout` 新增 `observation_date`、`快取更新於` 標籤改為 `排程更新於`、過期說明改講「資料觀測日」。
`page_find.py` 被舊鏈(`tests/test_me_p1_revert_chain.py::me_p1_revert_for` 及更舊者)以「新寫法 → 舊寫法」錨點還原成
各自的基底 sha256;D1 的改動落在它們的比對範圍之內 ⇒ 需在鏈頭**往前接一節**,先把 D1 換回
(比照 `tests/test_d2_staleness_revert_chain.py` 接在 `p4_revert_for` 開頭的作法;⛔ 不動任何舊表與舊基底 sha、不放寬任何斷言)。

基底 ＝ D1 開工前的 `b6d2ee4`(origin/main);`git show b6d2ee4:<檔> | sha256sum` 實算後寫死,測試不依賴 git。
其餘被 D1 動到的檔(`reader.py`／`_target_blocks.py`／`tab_sector_flow.py`)不被任何基底 sha 守衛釘住,不需還原組。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_PF_REL = "src/ui/views/page_find.py"

D1_BASE_SHA = {
    _PF_REL: "a2108b03dec81093fc8868a8f71c0af4645e74535ba7d8ddb2c8ae8eec39d1ac",
}

D1_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _PF_REL: (('    reason: str = ""\n'
      '    #: `updated_at`／`meta_updated_at` ＝ 排程（cron）**執行**時間，⛔ 不是資料日（D1，DEC-148：向後相容保留鍵，語意註明）。\n'
      '    updated_at: str = ""\n',
      '    reason: str = ""\n    updated_at: str = ""\n'),
     ('    stale_reason: str = ""\n'
      '    #: D1（DEC-148，additive）：可信的**資料觀測日** `YYYY-MM-DD`（L1 `metadata.last_updated`）；\n'
      '    #: 缺／無法解析／晚於今日／矛盾 ⇒ `""`（⛔ 不以 `updated_at` 頂替；畫面誠實顯示「資料日未提供」）。\n'
      '    observation_date: str = ""\n'
      '    n_days: str = ""\n',
      '    stale_reason: str = ""\n    n_days: str = ""\n'),
     ('        meta_updated_at=str(_view.get("meta_updated_at") or ""),\n'
      '        observation_date=str(_view.get("observation_date") or ""),   # D1：資料日只取可信觀測日\n'
      '        stale_reason=str(_view.get("stale_reason") or ""),\n',
      '        meta_updated_at=str(_view.get("meta_updated_at") or ""),\n'
      '        stale_reason=str(_view.get("stale_reason") or ""),\n'),
     ('    _facts: list[tuple[str, str]] = []\n'
      '    # D1（DEC-148，有意識的修改，⛔ 不是漏刪）：~~("快取更新於", flow.updated_at)~~ —— `updated_at` 是 cron 執行時間，\n'
      '    #   舊標籤讓人讀成資料日。→ 維持顯示該時戳，但標為「排程更新於」（執行時間，不是資料日；⛔ 不新增 facts 列，\n'
      '    #   資料日由 header chip／Basis.as_of 吃 `observation_date` 顯示）。\n'
      '    if flow.updated_at:\n',
      '    _facts: list[tuple[str, str]] = []\n    if flow.updated_at:\n'),
     ('    if flow.updated_at:\n        _facts.append(("排程更新於", flow.updated_at))\n    if flow.n_days:\n',
      '    if flow.updated_at:\n        _facts.append(("快取更新於", flow.updated_at))\n    if flow.n_days:\n'),
     ('            now=FLOW_STALE_NOW,\n'
      '            why=(f"資料觀測日距今已超過門檻或無法判定"\n'
      '                 f"（{flow.stale_reason or \'上游沒有給原因\'}；"\n',
      '            now=FLOW_STALE_NOW,\n'
      '            why=(f"盤後凍結任務的更新時戳距今已超過門檻"\n'
      '                 f"（{flow.stale_reason or \'上游沒有給原因\'}；"\n'),
     ('                 f"（{flow.stale_reason or \'上游沒有給原因\'}；"\n'
      '                 f"排程執行時戳 {flow.meta_updated_at or \'未知\'}，不是資料日）—— "\n'
      '                 "圖照畫，但別拿它當今天的資金流向讀"),\n',
      '                 f"（{flow.stale_reason or \'上游沒有給原因\'}；"\n'
      '                 f"metadata 時戳 {flow.meta_updated_at or \'未知\'}）—— "\n'
      '                 "圖照畫，但別拿它當今天的資金流向讀"),\n')),
}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def d1_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`(或 repo 相對路徑)與原始碼,換回 D1 之前的寫法(無 pair 則原樣;只套一次)。"""
    rel = _rel(file_path)
    pairs = D1_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} D1 還原組錨點漂移(各組出現次數 {counts};應全 1 或全 0)—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_d1_revert_is_exact_base_source():
    assert set(D1_REVERT_PAIRS) == set(D1_BASE_SHA)
    for rel in sorted(D1_REVERT_PAIRS):
        code = d1_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == D1_BASE_SHA[rel], rel


def test_d1_revert_is_idempotent():
    for rel in sorted(D1_REVERT_PAIRS):
        once = d1_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert d1_revert_for(rel, once) == once, rel


def test_d1_anchor_present_once_in_current_file():
    """D1 寫法真的在現行檔(恰 1 次);還原後 0 次 —— 防止還原組變成空轉。"""
    for rel, pairs in D1_REVERT_PAIRS.items():
        cur = (REPO / rel).read_text(encoding="utf-8")
        base = d1_revert_for(rel, cur)
        for new, _old in pairs:
            assert cur.count(new) == 1 and base.count(new) == 0, (rel, new[:60])


def test_chain_head_calls_d1_first():
    """原鏈頭 `p4_revert_for` 必須先呼叫本節(再往下才是 D2 守衛 → P4 → …;否則舊批次的基底 sha 守衛看到的是 D1 的新寫法)。"""
    import inspect

    from tests.test_p4_revert_chain import p4_revert_for
    src = inspect.getsource(p4_revert_for)
    assert src.index("d1_revert_for(file_path, code)") < src.index("d2stale_revert_for(file_path, code)")
