"""tests/test_xvext_revert_chain.py — XV 客戶裁示批（XV-H1-EXT／XV-H3／XV-H2-EXT／XV-M1，2026-10-28）的還原鏈新頭節。

為什麼需要：本批改了被舊鏈（`sheet_safety_revert_for` → … → `c1_revert_for`／`dec074_revert_for` 等）以
基底 sha 守衛的檔 ⇒ 在鏈頭**往前接一節**，先把本批改動換回（比照 `xview_revert_for` 接
`sheet_safety_revert_for` 的作法；⛔ 不動任何舊表與舊基底 sha）。

基底 ＝ `f3d77703`（本批開工前的 main）。pair 於產生時驗證「套用後逐字等於基底、
每個新寫法在現行檔恰出現 1 次、在基底 0 次」。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

XVEXT_BASE_SHA = {'shared/station_specs.py': 'c5747bae89fa1a1f744c302de34978b781553083aa5a5e33d357b9d47bd85fc3',
 'src/compute/notify/holdings_digest_message.py': 'a894b6ae8109c515b5b668e9621e737a4a16da94c8d65a01c1e2866697a5733f',
 'src/data/macro/macro_core.py': '68cb0fb283bb473031e423e47f0696dea0d02d871c3fea519d8a1a767a75ac9c',
 'src/services/dividend_station_service.py': '488dbb53ed9e2a2392c7bbd5b7f4ebf9d03dc03c468363219bfa92ebd34b01e3'}

XVEXT_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'shared/station_specs.py': (('\n'
                              '\n'
                              '# ══════════════════════════════════════════════════════════════════════\n'
                              '# XV-H1-EXT（客戶 2026-10-28 裁示 A）：missing ≠ HOLD；unavailable ≠ safe\n'
                              '# ══════════════════════════════════════════════════════════════════════\n'
                              '#: 缺資料標的的建議動作句。取代「⚪ 巡航：維持定期定額」「🟢 續抱：…」這類**持有結論**\n'
                              '#: —— 資料不足時不得以「續抱」當缺資料的替代結論。有充分資料的列一字不動。\n'
                              'INSUFFICIENT_ACTION_TEXT: str = "⬜ 資料不足／無法判定"\n'
                              '\n'
                              '#: L3 `build_station_rows` 在列上標「這列為什麼資料不足」的非顯示欄（同 `_detail` 慣例）。\n'
                              '#: 值 ＝ 下列原因常數的 tuple。⚠️ **只有資料不足時才有這一鍵** —— 資料完整的列逐鍵不變。\n'
                              'KEY_INSUFFICIENT: str = "_insufficient"\n'
                              '#: 該列**每一盞燈都判不出**（ETF：健檢四燈皆 ⚪ 且 235 落在巡航；個股：汰換燈 ⚪）。\n'
                              'INSUFF_ALL_UNJUDGED: str = "all_lights_unjudged"\n'
                              '#: 持有列缺現價（含現價資料異常被排除）。\n'
                              'INSUFF_NO_PRICE: str = "no_price"\n'
                              '#: 原因 → 給 ⑦ AI prompt／LINE 的事實短句（只講事實，不給結論）。\n'
                              'INSUFF_REASON_TEXT: dict = {\n'
                              '    INSUFF_ALL_UNJUDGED: "燈號全部判不出",\n'
                              '    INSUFF_NO_PRICE: "缺現價",\n'
                              '}\n',
                              ''),),
 'src/compute/notify/holdings_digest_message.py': (('import math\n', ''),
                                                   ('from shared import station_specs as SS\n', ''),
                                                   ('def _data_short(digest: dict) -> bool:\n'
                                                    '    """XV-H1-EXT（客戶 2026-10-28 裁示 A）：有抓取失敗或資料不足（燈全判不出／缺現價）的標的？\n'
                                                    '\n'
                                                    '    成立時正文**不印「續抱」**當缺資料的替代結論（missing ≠ HOLD；unavailable ≠ safe）。\n'
                                                    '    """\n'
                                                    '    return bool(digest.get("errors")) or bool(digest.get("insufficient"))\n'
                                                    '\n'
                                                    '\n',
                                                    ''),
                                                   ('        if _data_short(digest):\n'
                                                    '            # XV-H1-EXT：資料不足時「無紅燈」只是「判得出的沒有紅燈」，⛔ 不接「續抱」。\n'
                                                    '            return ["🔴 建議換出（持有紅燈汰弱）", "\u3000✅ 判得出的標的無紅燈（資料不足者未下結論）"]\n',
                                                    ''),
                                                   ('def _insufficient_line(digest: dict) -> list[str]:\n'
                                                    '    """XV-H1-EXT：資料不足／無法判定的標的（燈全判不出、缺現價）。空 → 略過。"""\n'
                                                    '    _ins = digest.get("insufficient") or []\n'
                                                    '    if not _ins:\n'
                                                    '        return []\n'
                                                    '    return [f"{SS.INSUFFICIENT_ACTION_TEXT}：" + "、".join(\n'
                                                    '        f"{_code(d)}（" + "、".join(SS.INSUFF_REASON_TEXT.get(_r, str(_r))\n'
                                                    '                                for _r in (d.get("原因") or ())) + "）" for d in _ins)]\n'
                                                    '\n'
                                                    '\n',
                                                    ''),
                                                   ('    XV-H1-EXT（客戶 2026-10-28 裁示 A）：但有抓取失敗或資料不足（`digest.insufficient`）時\n'
                                                    '    ⛔ 不印「續抱」，改講「判得出的標的無訊號、資料不足者未下結論」。\n',
                                                    ''),
                                                   ('    # ~~`_total = int(_num(digest.get("total")) or 0)`~~（XV-H1-EXT 順手修，⛔ '
                                                    '不是漏刪）：NaN／±inf\n'
                                                    '    # 是 truthy，`int(nan)` 拋 ValueError、`int(inf)` 拋 OverflowError → 整則推播炸掉。\n'
                                                    '    # 現：非有限值與非數一律當 0（＝不可判斷），走下方「未能判斷」路徑。\n'
                                                    '    _t_raw = _num(digest.get("total"))\n'
                                                    '    _total = int(_t_raw) if _t_raw is not None and math.isfinite(_t_raw) else 0\n',
                                                    '    _total = int(_num(digest.get("total")) or 0)   # 契約漂移防禦:非數 total → 0,不 '
                                                    'ValueError\n'),
                                                   ('                 _allocation_line(digest), _errors_line(digest), '
                                                    '_insufficient_line(digest)):\n',
                                                    '                 _allocation_line(digest), _errors_line(digest)):\n'),
                                                   ('    elif _no_action and _data_short(digest):\n'
                                                    '        # XV-H1-EXT（客戶 2026-10-28 裁示 A）：部分抓取失敗／燈全判不出／缺現價 → ⛔ 不印「續抱」\n'
                                                    '        # 當缺資料的替代結論；只講判得出的範圍，並把資料不足的標的指回上方清單。\n'
                                                    '        lines += ["", "📭 判得出的標的今日無換出／加碼／停利訊號；"\n'
                                                    '                      "資料不足或抓取失敗的標的未下結論（見上方清單）。"]\n',
                                                    '')),
 'src/data/macro/macro_core.py': (('\n'
                                   '\n'
                                   'def clear_success_caches() -> tuple[str, ...]:\n'
                                   '    """清掉本模組的**成功**快取（`_YF_CLOSE_CACHE`、`_FRED_CACHE`），回傳實際清了哪幾層。\n'
                                   '\n'
                                   '    XV-H2-EXT／XV-M1（客戶 2026-10-28 裁示）：側欄「🔄 強制刷新數據」原本只做\n'
                                   '    `st.cache_data.clear()`，本模組自建的成功快取（VIX／匯率等 Yahoo 收盤 1hr、FRED 30min）\n'
                                   '    沒有任何 production 清除路徑 ⇒ 按了刷新仍拿舊值。由 L6 `app.py` 該按鈕經 L3 `force_refresh_service` 呼叫。\n'
                                   '    ⛔ **刻意不清**失敗退避表（`_FRED_FAIL_CACHE`、`_YF_CLOSE_EMPTY_FAIL_CACHE`、\n'
                                   '    `_YF_OHLCV_FAIL_CACHE`／`_YF_OHLCV_OK_GEN_CACHE`）：v3 §02「失敗時退避、不連續轟炸來源」\n'
                                   '    不得因為使用者按了刷新就破功。讀寫持與抓取端同一把鎖。\n'
                                   '    """\n'
                                   '    with _FRED_CACHE_LOCK:\n'
                                   '        _FRED_CACHE.clear()\n'
                                   '    with _YF_CLOSE_CACHE_LOCK:\n'
                                   '        _YF_CLOSE_CACHE.clear()\n'
                                   '    return ("macro_core._FRED_CACHE", "macro_core._YF_CLOSE_CACHE")\n',
                                   ''),),
 'src/services/dividend_station_service.py': (('def _mark_insufficient(row: dict, *, ak: str, held: bool) -> None:\n'
                                               '    """XV-H1-EXT（客戶 2026-10-28 裁示 A：missing ≠ HOLD；unavailable ≠ safe）。就地標記。\n'
                                               '\n'
                                               '    資料不足的兩種情形（只有成立時才加 `SS.KEY_INSUFFICIENT`，資料完整的列逐鍵不變）：\n'
                                               '    - `SS.INSUFF_ALL_UNJUDGED`：該列每一盞燈都判不出 —— ETF：健檢四燈皆 ⚪（`健檢` 取最嚴重、\n'
                                               '      ⚪ 排最低，⇒ `健檢=="⚪"` 即四燈皆 ⚪）**且**建議分支落在巡航（⇒ 235 無加碼／停利，亦為 ⚪）；\n'
                                               '      個股：汰換燈 `健檢=="⚪"`（財報缺或契約漂移）。\n'
                                               '    - `SS.INSUFF_NO_PRICE`：持有列缺現價（含現價資料異常被排除，`現價` 為 None）。\n'
                                               '    只有當既有建議是**持有結論**（ETF 巡航「⚪ 巡航：維持定期定額」、個股 🟢「續抱」）時，\n'
                                               '    才把 `建議動作` 換成 `SS.INSUFFICIENT_ACTION_TEXT` —— 缺資料不得以「續抱」當替代結論。\n'
                                               '    可證明的結論（🔴 汰弱、加碼、停利、🟡 留意）與既有的資料不足句（個股「⚪ 財報資料不足…」）\n'
                                               '    一字不動；判燈規則與 `_action` 分支代碼不動。\n'
                                               '    """\n'
                                               '    _is_stock = ak == T.KIND_STOCK\n'
                                               '    _hold = (row.get("健檢") == "🟢") if _is_stock else (row.get("_action") == '
                                               'ds.ACTION_CRUISE)\n'
                                               '    _reasons = []\n'
                                               '    if row.get("健檢") == "⚪" and (_is_stock or row.get("_action") == ds.ACTION_CRUISE):\n'
                                               '        _reasons.append(SS.INSUFF_ALL_UNJUDGED)\n'
                                               '    if held and row.get("現價") is None:\n'
                                               '        _reasons.append(SS.INSUFF_NO_PRICE)\n'
                                               '    if not _reasons:\n'
                                               '        return\n'
                                               '    row[SS.KEY_INSUFFICIENT] = tuple(_reasons)\n'
                                               '    if _hold:\n'
                                               '        row["建議動作"] = SS.INSUFFICIENT_ACTION_TEXT\n'
                                               '\n'
                                               '\n',
                                               ''),
                                              ('            _mark_insufficient(_row, ak=ak, held=held)\n', ''),
                                              ('    # XV-H1-EXT（客戶 2026-10-28 裁示 A）：資料不足的列（`SS.KEY_INSUFFICIENT`，燈全判不出／\n'
                                               '    # 持有列缺現價）→ 列出代號與原因（**只有非空時才有這一鍵**，資料完整時 digest 逐鍵不變）。\n'
                                               '    # 下游（⑦ prompt、LINE 正文）據此不給「續抱」類組合層結論。抓取失敗列另在 errors。\n'
                                               '    _insufficient = [{"代號": str(r.get("代號", "")), "原因": tuple(r.get(SS.KEY_INSUFFICIENT) '
                                               'or ())}\n'
                                               '                     for r in (rows or [])\n'
                                               '                     if not r.get("_detail", {}).get("error") and '
                                               'r.get(SS.KEY_INSUFFICIENT)]\n'
                                               '    if _insufficient:\n'
                                               '        _out["insufficient"] = _insufficient\n',
                                               ''),
                                              ('\n'
                                               '\n'
                                               '#: XV-H1-EXT：資料不足（抓取失敗／燈全判不出／缺現價／無有效判斷檔）時取代「續抱」引導句。\n'
                                               '_INSUFFICIENT_INSTRUCTION: str = (\n'
                                               '    "有標的資料不足或抓取失敗,資料不足的標的請寫『資料不足／無法判定』,"\n'
                                               '    "不得給組合層『全部續抱』類總結,也不得自行補上缺少的資料。")\n',
                                               ''),
                                              ('    # ~~只看 total；部分失敗／燈全 ⚪／無現價**不在**此列（客戶 Z51/Z52 範圍，既有測試釘住）。~~\n'
                                               '    # ↑ 2026-10-28 客戶裁示 XV-H1-EXT 取代（有意識的變更，⛔ 不是漏刪）：三者現在也不放續抱句，見下。\n',
                                               '    # 只看 total；部分失敗／燈全 ⚪／無現價**不在**此列（客戶 Z51/Z52 範圍，既有測試釘住）。\n'),
                                              ('    # XV-H1-EXT（客戶 2026-10-28 裁示 A，取代 Z51/Z52 對「部分失敗／燈全判不出／缺現價仍帶續抱」的語意）：\n'
                                               '    # 「續抱」那句只在 total 有限且 ≥1、**無**抓取失敗、**無**燈全判不出、**無**缺現價時才放；\n'
                                               '    # 否則改放一句明確指示（資料不足者寫「資料不足／無法判定」、不得給組合層「全部續抱」類總結、\n'
                                               '    # 不得補資料）。只有 Z51/Z52 資料異常（`invalid`）時維持修前作法（兩句都不放）。\n'
                                               '    _ins = digest.get("insufficient") or []\n'
                                               '    _short = _no_judged or bool(digest.get("errors")) or bool(_ins)\n'
                                               '    _guide = (_INSUFFICIENT_INSTRUCTION if _short\n'
                                               '              else "" if _inv else "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。")\n',
                                               ''),
                                              ('        + _guide + "\\n"\n',
                                               '        + ("" if (_inv or _no_judged) else "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。") + "\\n"\n'),
                                              ('    if _ins:\n'
                                               '        _base += ("- 資料不足／無法判定："\n'
                                               '                  + "、".join(f"{d[\'代號\']}（" + "、".join(SS.INSUFF_REASON_TEXT.get(_r, '
                                               'str(_r))\n'
                                               '                                                         for _r in d.get("原因", ())) + "）"\n'
                                               '                             for d in _ins) + "\\n")\n',
                                               ''))}



def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def xvext_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = XVEXT_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} XV 客戶裁示批還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_xvext_revert_is_exact_base_source():
    assert set(XVEXT_REVERT_PAIRS) == set(XVEXT_BASE_SHA)
    for rel in sorted(XVEXT_REVERT_PAIRS):
        code = xvext_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == XVEXT_BASE_SHA[rel], rel


def test_xvext_revert_is_idempotent():
    for rel in sorted(XVEXT_REVERT_PAIRS):
        once = xvext_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert xvext_revert_for(rel, once) == once, rel


def test_chain_head_calls_xvext_first():
    """原鏈頭 `xview_revert_for` 必須先呼叫本節（再處理自己的表）；`sheet_safety_revert_for` 先呼叫 xview 節。"""
    import inspect

    from tests.test_sheet_safety_revert_chain import sheet_safety_revert_for
    from tests.test_xview_revert_chain import xview_revert_for
    src = inspect.getsource(xview_revert_for)
    assert src.index("xvext_revert_for(rel, code)") < src.index("XVIEW_REVERT_PAIRS.get(rel")
    ss = inspect.getsource(sheet_safety_revert_for)
    assert ss.index("xview_revert_for(rel, code)") < ss.index("nav1_revert_for(rel, code)")
