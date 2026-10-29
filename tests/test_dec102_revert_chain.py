"""tests/test_dec102_revert_chain.py — DEC-102（客戶 2026-10-28：XV-OLDUI-FX-REASON＝B／XV-LINE-VIX-LINE／
XV-FX-ROW-ACTION）批的還原鏈新頭節。

為什麼需要：本批改了被 `tests/test_xvext_revert_chain`（及其後的舊鏈）以基底 sha 守衛的檔 ⇒ 在鏈頭
**往前接一節**：`xvext_revert_for` 先呼叫本節把本批改動換回（比照 `xvext_revert_for` 接 `xview_revert_for`
的作法；⛔ 不動任何舊表與舊基底 sha）。另供本批 parity 測試取得「修前」模組（`base_module`）。

基底 ＝ `1e603094`（本批開工前的 main）。pair 於產生時驗證「套用後逐字等於基底、每個新寫法在現行檔
恰出現 1 次、在基底 0 次」。測試本身不呼叫 git（`tests/test_zz_test_portability.py`）。
"""
from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DEC102_BASE_SHA = {'src/ui/etf/etf_tab_dividend_station.py': '9554556c0ed8d1bd56ea0ce6feea04f61871c72f1e271fbc1c960714267445ee'}

DEC102_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'src/ui/etf/etf_tab_dividend_station.py': (('from shared import asset_currency_gate as FXG  # '
                                             'DEC-102(2)：外幣原因句（L0 唯一來源）\n',
                                             ''),
                                            ('        fx_excluded_codes,\n', ''),
                                            ('        _fx = fx_excluded_codes(_rows)\n'
                                             '        if _fx:\n'
                                             '            # DEC-102(2)（DEC-019 '
                                             '凍結的客戶核准例外，XV-OLDUI-FX-REASON＝B）：外幣／幣別未確認 → L3 不算總額，\n'
                                             '            #   ⛔ 不講成「持股沒有張數／均價／現價」；改用新 UI 同一 L0 '
                                             '客戶句＋未納入清單（不新寫文案）。\n'
                                             '            _note = f"{FXG.FX_PARTIAL_TEXT}\u3000'
                                             '{FXG.fx_excluded_text(_fx)}"\n'
                                             '        elif not (_held and all((r.get("_detail") or '
                                             '{}).get("error") for r in _held)):\n',
                                             '        if not (_held and all((r.get("_detail") or '
                                             '{}).get("error") for r in _held)):\n'),
                                            ('        compute_allocation_split, flag_take_profit, '
                                             'fx_excluded_codes)\n',
                                             '        compute_allocation_split, flag_take_profit)\n'),
                                            ('        _fx = fx_excluded_codes(rows)\n'
                                             '        if _fx:\n'
                                             '            # DEC-102(2)（DEC-019 '
                                             '凍結的客戶核准例外，XV-OLDUI-FX-REASON＝B）：同卡①，⛔ 不講成「未帶張數／均價」。\n'
                                             '            st.caption(f"📊 80/20 '
                                             '配置偏離：{FXG.FX_PARTIAL_TEXT}\u3000{FXG.fx_excluded_text(_fx)}")\n'
                                             '        elif _held and all((r.get("_detail") or '
                                             '{}).get("error") for r in _held):\n',
                                             '        if _held and all((r.get("_detail") or {}).get("error") '
                                             'for r in _held):\n'))}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def dec102_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = DEC102_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} DEC-102 批還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def base_module(rel: str, name: str) -> types.ModuleType:
    """`rel` 在本批開工前（`1e603094`）的模組（現行原始碼套上 `dec102_revert_for` 後 exec）。"""
    assert rel in DEC102_BASE_SHA
    code = dec102_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
    m = types.ModuleType(name)
    m.__file__ = str(REPO / rel)
    sys.modules[name] = m
    exec(compile(code, str(REPO / rel), "exec"), m.__dict__)
    return m


def test_dec102_revert_is_exact_base_source():
    assert set(DEC102_REVERT_PAIRS) == set(DEC102_BASE_SHA)
    for rel in sorted(DEC102_REVERT_PAIRS):
        code = dec102_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == DEC102_BASE_SHA[rel], rel


def test_dec102_revert_is_idempotent():
    for rel in sorted(DEC102_REVERT_PAIRS):
        once = dec102_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert dec102_revert_for(rel, once) == once, rel


def test_chain_head_calls_dec102_first():
    """`xvext_revert_for` 必須先呼叫本節（再處理自己的表）。"""
    import inspect

    from tests.test_xvext_revert_chain import xvext_revert_for
    src = inspect.getsource(xvext_revert_for)
    assert src.index("dec102_revert_for(file_path, code)") < src.index("XVEXT_REVERT_PAIRS.get(rel")
