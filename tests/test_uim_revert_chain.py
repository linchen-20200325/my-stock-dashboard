"""tests/test_uim_revert_chain.py — UI-M（📊 市場頁落地，2026-10-29）的還原鏈新頭節。

為什麼需要：本批改了被舊鏈以基底 sha 守衛的檔（`src/ui/views/page_market.py` 被 `tests/test_nav1_revert_chain.py`
管；`src/compute/macro/macro_helpers.py` 被 `tests/test_dec074_revert_chain.py` 管）⇒ 在鏈頭**往前接一節**，
先把本批改動換回（比照 `asof_revert_for`／`dec102_revert_for` 的作法；⛔ 不動任何舊表與舊基底 sha）。
`xvext_revert_for` 第一步呼叫本節（再往下是 dec102 → asof → xvext 自己的表 → …）。

基底 ＝ `d0482441`（main，UI-M 開工前）。pair 由 `difflib` 分組、最小唯一上下文產生，產生時驗證：
「套用後逐字等於基底、每個新寫法在現行檔恰出現 1 次、套用後 0 次」。基底 sha 寫死以免測試依賴 git。

⚠️ 只套一次（idempotent）：本批改到的檔同時被好幾條鏈管，同一份程式碼可能經過兩個掛點。判定（整檔一起看）：
每一組的 `新寫法` 都恰好出現一次 ⇒ 換回；都 0 次 ⇒ 已被前一個掛點換回；其餘 ⇒ AssertionError（錨點漂移，須重產）。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

UIM_BASE_SHA = {'src/compute/macro/macro_helpers.py': '2f497bfdf4891d69f8116311ca72ddf773da1c4a976b71cc34a510c0057ce8b9'}

UIM_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'src/compute/macro/macro_helpers.py': (('    -------\n'
                                         '    dict: {bucket: {level, label, headline, color, emoji, '
                                         'details:[...], main_key}}，\n'
                                         '          bucket ∈ long/mid/short/chips/news。`main_key`（UI-M '
                                         '加性）＝桶燈號的主因燈\n'
                                         '          `DangerSpec.key`；桶全綠／全灰 → None。\n'
                                         '\n',
                                         '    -------\n'
                                         '    dict: {bucket: {level, label, headline, color, emoji, '
                                         'details:[...]}}，\n'
                                         '          bucket ∈ long/mid/short/chips/news。\n'
                                         '\n'),
                                        ('            "details": details,\n'
                                         '            # UI-M（2026-10-29，加性）：外露「主因燈 key」＝上面 headline／label '
                                         '已經在用的那一盞 `d0`\n'
                                         '            #   （桶內既有 worst-of，超標幅度最大者）。桶全綠／全灰時 `d0 is None` → '
                                         'None。\n'
                                         '            #   既有各鍵的值一個字都沒動；消費端（📊 市場頁圖 D／今日主要風險）據此取方向，⛔ 不在 L5 '
                                         '重算規則。\n'
                                         '            "main_key": d0["key"] if d0 is not None else None,\n'
                                         '        }\n',
                                         '            "details": details,\n        }\n'))}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def uim_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 UI-M 之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = UIM_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} UI-M 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_uim_revert_is_exact_base_source():
    assert set(UIM_REVERT_PAIRS) == set(UIM_BASE_SHA)
    for rel in sorted(UIM_REVERT_PAIRS):
        code = uim_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == UIM_BASE_SHA[rel], rel


def test_uim_revert_is_idempotent():
    for rel in sorted(UIM_REVERT_PAIRS):
        once = uim_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert uim_revert_for(rel, once) == once, rel


def test_chain_head_calls_uim_first():
    """`xvext_revert_for` 必須先呼叫本節（再處理 dec102／asof／自己的表）。"""
    import inspect

    from tests.test_xvext_revert_chain import xvext_revert_for
    src = inspect.getsource(xvext_revert_for)
    assert src.index("uim_revert_for(file_path, code)") < src.index("dec102_revert_for(file_path, code)")
