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
 'src/services/dividend_station_service.py': '488dbb53ed9e2a2392c7bbd5b7f4ebf9d03dc03c468363219bfa92ebd34b01e3',
 'src/services/portfolio_deep_service.py': 'f4d2c99c5498371fe9000e0e291079623b40bb6c3c331f7b97ed8ab5f98f3d96',
 'src/services/weekly_review_service.py': '3615ff1ebe88d744ef13508cccb11bf35c70aafea3d6a8659d820544d9a68d2e',
 'src/ui/views/page_hold.py': 'e25609612b0a426896f4f89aa6f559a7906632378a5f0176e080b2aa6b5897e1'}

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
                              '#: QA 回修 #7：持有列缺現價、但**結論可證明**（🔴 汰弱／加碼／停利／🟡 留意，建議動作未被換成 ⬜）\n'
                              '#: 的非顯示欄。⚠️ 這種列**不進** `KEY_INSUFFICIENT`（不得被列成「無法判定」），只另列事實句\n'
                              '#: 「缺現價（結論不受影響）」。只有成立時才有這一鍵。\n'
                              'KEY_PRICE_MISSING_KEPT: str = "_price_missing_kept"\n'
                              '#: 上一鍵的事實句（⑦ prompt／LINE 共用）。\n'
                              'PRICE_MISSING_KEPT_TEXT: str = "缺現價（結論不受影響）"\n'
                              '#: 原因 → 給 ⑦ AI prompt／LINE 的事實短句（只講事實，不給結論）。\n'
                              'INSUFF_REASON_TEXT: dict = {\n'
                              '    INSUFF_ALL_UNJUDGED: "燈號全部判不出",\n'
                              '    INSUFF_NO_PRICE: "缺現價",\n'
                              '}\n',
                              ''),),
 'src/compute/notify/holdings_digest_message.py': (('import math\n', ''),
                                                   ('from shared import asset_currency_gate as FXG\n', ''),
                                                   ('from shared import station_specs as SS\n', ''),
                                                   ('def _data_short(digest: dict) -> bool:\n'
                                                    '    """XV-H1-EXT（客戶 2026-10-28 裁示 A）：有抓取失敗或資料不足（燈全判不出／缺現價）的標的？\n'
                                                    '\n'
                                                    '    成立時正文**不印「續抱」**當缺資料的替代結論（missing ≠ HOLD；unavailable ≠ safe）。\n'
                                                    '    """\n'
                                                    '    # QA 回修 #2：持有列輸入／燈資料異常（`invalid`，批 Z49～Z52）同樣是「判不出來」，不是「沒事」。\n'
                                                    '    return (bool(digest.get("errors")) or bool(digest.get("insufficient"))\n'
                                                    '            or bool(digest.get("price_missing_kept")) or '
                                                    'bool(digest.get("invalid")))\n'
                                                    '\n'
                                                    '\n',
                                                    ''),
                                                   ('        if _data_short(digest):\n'
                                                    '            # XV-H1-EXT：資料不足時「無紅燈」只是「判得出的沒有紅燈」，⛔ 不接「續抱」。\n'
                                                    '            return ["🔴 建議換出（持有紅燈汰弱）", "\u3000✅ 判得出的標的無紅燈（資料不足者未下結論）"]\n',
                                                    ''),
                                                   ('        _fx = digest.get("fx_excluded") or []\n'
                                                    '        if _fx:\n'
                                                    '            # XV-H3（客戶 2026-10-28 裁示 A）：外幣／幣別未確認資產未納入 → 不印比例數字。\n'
                                                    '            return [f"⚖️ 配置：{FXG.FX_PARTIAL_TEXT}（{FXG.fx_excluded_text(_fx)}）"]\n',
                                                    ''),
                                                   ('\n'
                                                    '\n'
                                                    'def _insufficient_line(digest: dict) -> list[str]:\n'
                                                    '    """XV-H1-EXT：資料不足／無法判定的標的（燈全判不出、缺現價）。空 → 略過。"""\n'
                                                    '    _ins = digest.get("insufficient") or []\n'
                                                    '    _out: list[str] = []\n'
                                                    '    # QA 回修 #11：持有／觀察清單分開標明。#7：只列建議動作真的被換成 ⬜ 的標的。\n'
                                                    '    for _lbl, _grp in (("持有", [d for d in _ins if d.get("held", True)]),\n'
                                                    '                       ("觀察清單", [d for d in _ins if not d.get("held", True)])):\n'
                                                    '        if _grp:\n'
                                                    '            _out.append(f"{SS.INSUFFICIENT_ACTION_TEXT}（{_lbl}）：" + "、".join(\n'
                                                    '                f"{_code(d)}（" + "、".join(SS.INSUFF_REASON_TEXT.get(_r, str(_r))\n'
                                                    '                                        for _r in (d.get("原因") or ())) + "）" for d in '
                                                    '_grp))\n'
                                                    '    _kept = digest.get("price_missing_kept") or []\n'
                                                    '    if _kept:\n'
                                                    '        _out.append(f"ℹ️ {SS.PRICE_MISSING_KEPT_TEXT}：" + "、".join(str(_c) for _c in '
                                                    '_kept))\n'
                                                    '    return _out\n'
                                                    '\n'
                                                    '\n'
                                                    'def _invalid_line(digest: dict) -> list[str]:\n'
                                                    '    """QA 回修 #2：資料異常未判的標的（與 ⑦ prompt「- 資料異常未判：」同一份 digest、同一種格式）。空 → 略過。"""\n'
                                                    '    _inv = digest.get("invalid") or []\n'
                                                    '    if not _inv:\n'
                                                    '        return []\n'
                                                    '    return ["⚠️ 資料異常未判：" + "、".join(\n'
                                                    '        f"{_code(d)}（" + "\u3000".join(f"{_l}：{_t}" for _l, _t in (d.get("項目") or '
                                                    '())) + "）"\n'
                                                    '        for d in _inv)]\n',
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
                                                    '_invalid_line(digest),\n'
                                                    '                 _insufficient_line(digest)):\n',
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
                                   '    XV-H2-EXT／XV-M1（AI 總管決定（DEC-101(5) 授權邊界內），2026-10-28）：側欄「🔄 強制刷新數據」原本只做\n'
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
 'src/services/dividend_station_service.py': (('from shared import asset_currency_gate as FXG\n', ''),
                                              ('def _mark_insufficient(row: dict, *, ak: str, held: bool) -> None:\n'
                                               '    """XV-H1-EXT（客戶 2026-10-28 裁示 A：missing ≠ HOLD；unavailable ≠ safe）。就地標記。\n'
                                               '\n'
                                               '    資料不足的兩種情形（只有成立時才加 `SS.KEY_INSUFFICIENT`，資料完整的列逐鍵不變）：\n'
                                               '    - `SS.INSUFF_ALL_UNJUDGED`：該列每一盞燈都判不出 —— ETF：健檢四燈皆 ⚪（`健檢` 取最嚴重、\n'
                                               '      ⚪ 排最低，⇒ `健檢=="⚪"` 即四燈皆 ⚪）**且**建議分支落在巡航（⇒ 235 無加碼／停利，亦為 ⚪）；\n'
                                               '      個股：汰換燈 `健檢=="⚪"`（財報缺或契約漂移）。\n'
                                               '    - `SS.INSUFF_NO_PRICE`：持有列缺現價（含現價資料異常被排除，`現價` 為 None）。\n'
                                               '    `建議動作` 換成 `SS.INSUFFICIENT_ACTION_TEXT` 的列：既有建議是**持有結論**（ETF 巡航「⚪ 巡航：\n'
                                               '    維持定期定額」、個股 🟢「續抱」）、或個股汰換燈 ⚪（財報資料不足，本來就無法判定；原句移到\n'
                                               '    `_detail["原建議動作"]` 保留）—— 缺資料不得以「續抱」當替代結論。\n'
                                               '    QA 回修 #7：**只有真的被換成 ⬜ 的列**才帶 `SS.KEY_INSUFFICIENT`（才會被列成「無法判定」）；\n'
                                               '    可證明的結論（🔴 汰弱、加碼、停利、🟡 留意）一字不動、⛔ 不列入「無法判定」——\n'
                                               '    持有且缺現價者改帶 `SS.KEY_PRICE_MISSING_KEPT`（事實句「缺現價（結論不受影響）」）。\n'
                                               '    判燈規則與 `_action` 分支代碼不動。\n'
                                               '    """\n'
                                               '    _is_stock = ak == T.KIND_STOCK\n'
                                               '    _hold = (row.get("健檢") == "🟢") if _is_stock else (row.get("_action") == '
                                               'ds.ACTION_CRUISE)\n'
                                               '    _unjudged = row.get("健檢") == "⚪" and (_is_stock or row.get("_action") == '
                                               'ds.ACTION_CRUISE)\n'
                                               '    _no_price = held and row.get("現價") is None\n'
                                               '    _replace = _unjudged or (_no_price and _hold)\n'
                                               '    if _replace:\n'
                                               '        row[SS.KEY_INSUFFICIENT] = tuple(\n'
                                               '            _r for _r, _on in ((SS.INSUFF_ALL_UNJUDGED, _unjudged), (SS.INSUFF_NO_PRICE, '
                                               '_no_price))\n'
                                               '            if _on)\n'
                                               '        if not _hold and isinstance(row.get("_detail"), dict):\n'
                                               '            row["_detail"]["原建議動作"] = row.get("建議動作", "")\n'
                                               '        row["建議動作"] = SS.INSUFFICIENT_ACTION_TEXT\n'
                                               '    elif _no_price:\n'
                                               '        row[SS.KEY_PRICE_MISSING_KEPT] = True\n'
                                               '\n'
                                               '\n',
                                               ''),
                                              ('            if held and not FXG.is_confirmed_twd_ticker(tk):\n'
                                               '                # XV-H3（客戶 2026-10-28 裁示 A）：幣別未確認（外幣／看不出來）→ 不得與 TWD 加總；\n'
                                               '                # 成本幣別未定義 ⇒ 損益% 亦不可判定。市值／損益% 一律 None（⛔ 不換算、不猜匯率）。\n'
                                               '                _row[FXG.KEY_FX_UNCONFIRMED] = True\n'
                                               '                _row["市值"] = None\n'
                                               '                _row["損益%"] = None\n'
                                               '            _mark_insufficient(_row, ak=ak, held=held)\n',
                                               ''),
                                              ('# ── XV-H3：幣別未確認的持有列（不得與 TWD 加總）────────────────────────────\n'
                                               'def fx_excluded_codes(rows: list[dict]) -> list[str]:\n'
                                               '    """持有、非整批抓取失敗、且被 `build_station_rows` 標了 `FXG.KEY_FX_UNCONFIRMED` 的列代號（保序去重）。\n'
                                               '\n'
                                               '    XV-H3（客戶 2026-10-28 裁示 A）：只要非空，總市值／未實現損益合計／80/20 一律**不算**\n'
                                               '    （⛔ 不把剩餘台股包裝成完整組合）；畫面、LINE、AI 改講 `FXG.FX_PARTIAL_TEXT` ＋ 未納入清單。\n'
                                               '    判定只走 L0 `asset_currency_gate.is_confirmed_twd_ticker`（同一把尺，見該檔）。\n'
                                               '    """\n'
                                               '    return list(dict.fromkeys(\n'
                                               '        str(r.get("代號", "")) for r in (rows or [])\n'
                                               '        if r.get("held") and not (r.get("_detail") or {}).get("error")\n'
                                               '        and r.get(FXG.KEY_FX_UNCONFIRMED)))\n'
                                               '\n'
                                               '\n',
                                               ''),
                                              ('    XV-H3（客戶 2026-10-28 裁示 A）：有任何幣別未確認的持有列（`fx_excluded_codes` 非空）→ 回 `None`\n'
                                               '    （⛔ 不把剩餘台股的總額當成整個組合；由呼叫端講 `FX_PARTIAL_TEXT`）。\n',
                                               ''),
                                              ('    """\n    if fx_excluded_codes(rows):\n        return None\n    _cost = _value = 0.0\n',
                                               '    """\n    _cost = _value = 0.0\n'),
                                              ('    XV-H3（客戶 2026-10-28 裁示 A）：有任何幣別未確認的持有列 → None（⛔ 不顯示不完整的比例）。\n', ''),
                                              ('    """\n    if fx_excluded_codes(rows):\n        return None\n    _core = _sat = 0.0\n',
                                               '    """\n    _core = _sat = 0.0\n'),
                                              ('    # XV-H1-EXT（客戶 2026-10-28 裁示 A）：資料不足的列（`SS.KEY_INSUFFICIENT`，燈全判不出／\n'
                                               '    # 持有列缺現價）→ 列出代號與原因（**只有非空時才有這一鍵**，資料完整時 digest 逐鍵不變）。\n'
                                               '    # 下游（⑦ prompt、LINE 正文）據此不給「續抱」類組合層結論。抓取失敗列另在 errors。\n'
                                               '    # QA 回修 #11：每筆標明持有／觀察清單（`held`）。#7：只收建議動作真的被換成 ⬜ 的列。\n'
                                               '    _insufficient = [{"代號": str(r.get("代號", "")), "原因": tuple(r.get(SS.KEY_INSUFFICIENT) '
                                               'or ()),\n'
                                               '                      "held": bool(r.get("held"))}\n'
                                               '                     for r in (rows or [])\n'
                                               '                     if not r.get("_detail", {}).get("error") and '
                                               'r.get(SS.KEY_INSUFFICIENT)]\n'
                                               '    if _insufficient:\n'
                                               '        _out["insufficient"] = _insufficient\n'
                                               '    # QA 回修 #7：持有列缺現價、但結論可證明（未換成 ⬜）→ 另列事實（只有非空才有這一鍵）。\n'
                                               '    _kept = [str(r.get("代號", "")) for r in (rows or [])\n'
                                               '             if not r.get("_detail", {}).get("error") and '
                                               'r.get(SS.KEY_PRICE_MISSING_KEPT)]\n'
                                               '    if _kept:\n'
                                               '        _out["price_missing_kept"] = _kept\n'
                                               '    # XV-H3：幣別未確認、未納入總額／比例的持有列（只有非空才有這一鍵；`allocation` 此時為 None）。\n'
                                               '    _fx = fx_excluded_codes(rows)\n'
                                               '    if _fx:\n'
                                               '        _out["fx_excluded"] = _fx\n',
                                               ''),
                                              ('\n'
                                               '\n'
                                               '#: XV-H1-EXT：資料不足（抓取失敗／燈全判不出／缺現價／無有效判斷檔）時取代「續抱」引導句。\n'
                                               '_INSUFFICIENT_INSTRUCTION: str = (\n'
                                               '    "有標的資料不足或抓取失敗,列在『資料不足／無法判定』的標的請寫『資料不足／無法判定』,"\n'
                                               '    "其餘已列出的結論照原樣講,不得給組合層『全部續抱』類總結,也不得自行補上缺少的資料。")\n',
                                               ''),
                                              ('    # ~~只看 total；部分失敗／燈全 ⚪／無現價**不在**此列（客戶 Z51/Z52 範圍，既有測試釘住）。~~\n'
                                               '    # ↑ 2026-10-28 客戶裁示 XV-H1-EXT 取代（有意識的變更，⛔ 不是漏刪）：三者現在也不放續抱句，見下。\n',
                                               '    # 只看 total；部分失敗／燈全 ⚪／無現價**不在**此列（客戶 Z51/Z52 範圍，既有測試釘住）。\n'),
                                              ('    # XV-H1-EXT（客戶 2026-10-28 裁示 A，取代 Z51/Z52 對「部分失敗／燈全判不出／缺現價仍帶續抱」的語意）：\n'
                                               '    # 「續抱」那句只在 total 有限且 ≥1、**無**抓取失敗、**無**燈全判不出、**無**缺現價時才放；\n'
                                               '    # 否則改放一句明確指示（資料不足者寫「資料不足／無法判定」、不得給組合層「全部續抱」類總結、\n'
                                               '    # 不得補資料）。只有 Z51/Z52 資料異常（`invalid`）時維持修前作法（兩句都不放）。\n'
                                               '    _ins = digest.get("insufficient") or []\n'
                                               '    _kept = digest.get("price_missing_kept") or []\n'
                                               '    _short = _no_judged or bool(digest.get("errors")) or bool(_ins) or bool(_kept)\n'
                                               '    _guide = (_INSUFFICIENT_INSTRUCTION if _short\n'
                                               '              else "" if _inv else "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。")\n',
                                               ''),
                                              ('        + _guide + "\\n"\n',
                                               '        + ("" if (_inv or _no_judged) else "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。") + "\\n"\n'),
                                              ('    for _lbl, _grp in (("持有", [d for d in _ins if d.get("held", True)]),\n'
                                               '                       ("觀察清單", [d for d in _ins if not d.get("held", True)])):\n'
                                               '        if _grp:\n'
                                               '            _base += (f"- 資料不足／無法判定（{_lbl}）："\n'
                                               '                      + "、".join(f"{d[\'代號\']}（" + "、".join(SS.INSUFF_REASON_TEXT.get(_r, '
                                               'str(_r))\n'
                                               '                                                             for _r in d.get("原因", ())) + '
                                               '"）"\n'
                                               '                                 for d in _grp) + "\\n")\n'
                                               '    if _kept:\n'
                                               '        _base += f"- {SS.PRICE_MISSING_KEPT_TEXT}：{\'、\'.join(str(_c) for _c in '
                                               '_kept)}\\n"\n'
                                               '    _fx = digest.get("fx_excluded") or []\n'
                                               '    if _fx:\n'
                                               '        # XV-H3（客戶 2026-10-28 裁示 A）：外幣／幣別未確認資產不進總額 ⇒ AI 拿不到混幣總額，\n'
                                               '        # 只拿到「哪幾檔未納入、為什麼、比例無法完整判定」這個事實（⛔ 不送比例數字）。\n'
                                               '        _base += (f"- 未納入總市值與配置比例：{FXG.fx_excluded_text(_fx).removeprefix(\'未納入：\')}"\n'
                                               '                  "（總市值／配置比例無法完整判定）\\n")\n',
                                               '')),
 'src/services/portfolio_deep_service.py': (('import functools\n', ''),
                                            ('from dataclasses import dataclass, field, replace as _dc_replace\n',
                                             'from dataclasses import dataclass, field\n'),
                                            ('from shared import asset_currency_gate as FXG\n', ''),
                                            ('def _is_fx_unconfirmed(row: dict) -> bool:\n'
                                             '    """XV-H3（客戶 2026-10-28 裁示 A）：持有、非整批失敗、且代號**不能確定是台股**（L0\n'
                                             '    `asset_currency_gate.is_confirmed_twd_ticker`，與 `dividend_station_service` 同一把尺）。\n'
                                             '    這種列**不得**與 TWD 資產加總／算權重（⛔ 不換算、不猜匯率）。"""\n'
                                             '    return (bool(row.get("held")) and not _row_failed(row)\n'
                                             '            and not FXG.is_confirmed_twd_ticker(row.get("代號")))\n'
                                             '\n'
                                             '\n'
                                             'def _fx_excluded(rows) -> tuple[str, ...]:\n'
                                             '    """被 XV-H3 排除的持有列代號（保序去重）。"""\n'
                                             '    return tuple(dict.fromkeys(str(_r.get("代號", "")) for _r in (rows or [])\n'
                                             '                               if isinstance(_r, dict) and _is_fx_unconfirmed(_r)))\n'
                                             '\n'
                                             '\n'
                                             'def _attach_fx(fn):\n'
                                             '    """三支 public 函式的結果補上 `fx_excluded`（非空時）。結果型別與其餘欄位一字不動。"""\n'
                                             '    @functools.wraps(fn)\n'
                                             '    def _wrapped(rows, *args, **kwargs):\n'
                                             '        _res = fn(rows, *args, **kwargs)\n'
                                             '        _fx = _fx_excluded(rows)\n'
                                             '        return _dc_replace(_res, fx_excluded=_fx) if _fx else _res\n'
                                             '    return _wrapped\n'
                                             '\n'
                                             '\n',
                                             ''),
                                            ('        if _is_fx_unconfirmed(_r):      # XV-H3：外幣／幣別未確認 → 不進權重與總市值\n            continue\n',
                                             ''),
                                            ('        # XV-H3：對照值同樣只算台股那一批（L3 `compute_portfolio_totals` 見到幣別未確認列會回 None；\n'
                                             '        # 本檔已把它們排出權重 ⇒ 兩邊用同一批列對帳）。\n'
                                             '        _totals = compute_portfolio_totals(\n'
                                             '            [_r for _r in (rows or []) if not (isinstance(_r, dict) and '
                                             '_is_fx_unconfirmed(_r))])\n',
                                             '        _totals = compute_portfolio_totals(list(rows or []))\n'),
                                            ('    #: XV-H3（加性）：幣別未確認、未納入權重與總市值的持有列代號。`repr=False, compare=False` 理由同上。\n'
                                             '    fx_excluded: tuple[str, ...] = field(default=(), repr=False, compare=False)\n',
                                             ''),
                                            ('\n@_attach_fx\ndef get_portfolio_stress(rows, *, drop_pct: float | None = None,\n',
                                             '\ndef get_portfolio_stress(rows, *, drop_pct: float | None = None,\n'),
                                            ('    #: XV-H3（加性）：同 `StressResult.fx_excluded`。\n'
                                             '    fx_excluded: tuple[str, ...] = field(default=(), repr=False, compare=False)\n',
                                             ''),
                                            ('\n@_attach_fx\ndef get_portfolio_var(rows, *, strict: bool = False) -> VarResult:\n',
                                             '\ndef get_portfolio_var(rows, *, strict: bool = False) -> VarResult:\n'),
                                            ('    income_tax_included: bool = False\n    @property\n',
                                             '    income_tax_included: bool = False\n\n    @property\n'),
                                            ('    ⚠️ XV-H3（客戶 2026-10-28 裁示 A）：本路徑**本來就**不把海外標的混進 TWD 總額（下一行），\n'
                                             '    覆蓋率與 `overseas`／`excluded_tickers` 已揭露 ⇒ 不另套 `asset_currency_gate`（壓測／VaR 有套）。\n',
                                             '')),
 'src/services/weekly_review_service.py': (('    # QA 回修 #3（XV-H1-EXT 同一原則：missing ≠ HOLD）：燈號 ⚪ 的列（抓取失敗／價格資料不足／\n'
                                            '    # 樣本不足／非台股代號…）是**判不出來**，⛔ 不得被算進「均無連續落後（續抱觀察）」的 blanket 句。\n'
                                            '    _unjudged = [_r for _r in _rows if str(_r.get("燈號", "")).startswith("⚪")]\n'
                                            '    _n_judged = len(_rows) - len(_unjudged)\n',
                                            ''),
                                           ('    elif not _unjudged:\n', '    else:\n'),
                                           ('    elif _n_judged:\n'
                                            '        # 判得出的照講事實，但 ⛔ 不接「續抱觀察」（旁邊還有判不出的，不是整份清單的結論）。\n'
                                            '        _out.append(f"✅ 判得出的 {_n_judged}/{len(_rows)} 檔無連續落後")\n'
                                            '    if _rows and _unjudged:\n'
                                            '        _out.append("⬜ 資料不足／無法判定：" + "、".join(\n'
                                            '            f"{_r.get(\'代號\')}（{str(_r.get(\'燈號\', \'\')).removeprefix(\'⚪\').strip() or '
                                            '\'原因不明\'}）"\n'
                                            '            for _r in _unjudged))\n',
                                            '')),
 'src/ui/views/page_hold.py': (('    MISS_NOT_APPLICABLE,\n', ''),
                               ('from shared.asset_currency_gate import (\n'
                                '    FX_PARTIAL_TEXT,\n'
                                '    KEY_FX_UNCONFIRMED,\n'
                                '    fx_excluded_text,\n'
                                ')\n',
                                ''),
                               ('#: XV-H3（客戶 2026-10-28 裁示 A）：外幣／幣別未確認資產未納入時，總市值／配置比例處的客戶句。\n'
                                '#: `Note` 文案不得帶狀態 glyph（⬜ 是「尚未載入」的 glyph）⇒ Note 用去掉 ⬜ 的同一句；\n'
                                '#: 逐字含 ⬜ 的 `FX_PARTIAL_TEXT` 放在卡的 fact 列（L0 `asset_currency_gate` 唯一來源）。\n'
                                'FX_PARTIAL_NOW: str = FX_PARTIAL_TEXT.removeprefix("⬜").strip()\n'
                                '#: 同上的「去哪補」：目前沒有使用者可執行的出口（匯率來源／時點／成本幣別另開 Gate 定義）。\n'
                                'FX_PARTIAL_WHERE: str = (f"{NO_EXIT_MARKER} —— 外幣資產的匯率來源、時點與成本幣別尚未定義，"\n'
                                '                         "定義前本站不換算、不計入")\n'
                                '#: fact 列標籤（總市值／配置比例那一格、未納入清單那一格）。\n'
                                'FX_PARTIAL_FACT: str = "總市值／配置比例"\n'
                                'FX_EXCLUDED_FACT: str = "未納入"\n'
                                '\n'
                                '\n'
                                'def _fx_codes(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:\n'
                                '    """XV-H3：被 L3 標了 `KEY_FX_UNCONFIRMED` 的持有列代號（條件同 L3 `fx_excluded_codes`：\n'
                                '    持有、非整批抓取失敗；去重保序）。⛔ 本頁不自己判幣別 —— 只讀 L3 標記。"""\n'
                                '    return tuple(dict.fromkeys(\n'
                                '        str(_r.get("代號", "")) for _r in rows\n'
                                '        if _r.get("held") and not (_r.get("_detail") or {}).get("error")\n'
                                '        and _r.get(KEY_FX_UNCONFIRMED)))\n'
                                '\n'
                                '\n'
                                'def _fx_facts(codes: Sequence[str]) -> list[tuple[str, str]]:\n'
                                '    """XV-H3 的兩列 fact：`⬜ 部分外幣資產未納入…`（逐字）＋「VOO、BND｜原因：…」。"""\n'
                                '    if not codes:\n'
                                '        return []\n'
                                '    return [(FX_PARTIAL_FACT, FX_PARTIAL_TEXT),\n'
                                '            (FX_EXCLUDED_FACT, fx_excluded_text(codes).removeprefix("未納入："))]\n',
                                ''),
                               ('    # XV-H3（客戶 2026-10-28 裁示 A）：有外幣／幣別未確認的持有列 → L3 總額回 None（⛔ 不把剩餘台股\n'
                                '    # 包裝成整個組合）；這一格改列客戶句 ＋ 未納入清單（排在資料異常那句之前）。\n'
                                '    _fx = _fx_codes(station.rows)\n'
                                '    if _fx:\n'
                                '        return _fx_facts(_fx) + ([("未實現損益／總市值", _invalid_why(_bad))] if _bad else [])\n',
                                ''),
                               ('    # XV-H3：外幣／幣別未確認資產未納入 → 比例不畫（L3 回 None），列客戶句與未納入清單。\n'
                                '    _facts = _fx_facts(_fx_codes(station.rows)) + _facts\n',
                                ''),
                               ('        # QA 回修 #6：外幣／幣別未確認 → 「不適用 · 重跑無效」（#8，既有徽章；重跑一樣算不出，\n'
                                '        # 與「去哪補」的「沒有你可以執行的出口」一致），⛔ 不落在「缺漏 · 可重跑」。\n'
                                '        reason=(MISS_FETCH_FAILED if _uncounted\n'
                                '                else MISS_NOT_APPLICABLE if _fx_codes(station.rows) else ""))\n',
                                '        reason=MISS_FETCH_FAILED if _uncounted else "")\n'),
                               ('    elif _fx_codes(station.rows):\n'
                                '        # XV-H3（客戶 2026-10-28 裁示 A）：外幣／幣別未確認 → L3 不算比例（⛔ 不把剩餘台股包裝成完整 80/20）。\n'
                                '        _note = Note(now=FX_PARTIAL_NOW, why=fx_excluded_text(_fx_codes(station.rows)),\n'
                                '                     where=FX_PARTIAL_WHERE)\n',
                                ''),
                               ('    _bits += _fx_degraded_bits(result)\n', ''),
                               ('\n'
                                '\n'
                                'def _fx_degraded_bits(result: Any) -> list[tuple[str, str]]:\n'
                                '    """XV-H3（客戶 2026-10-28 裁示 A）：L3 回報有外幣／幣別未確認的持有列沒進這個數字（`fx_excluded`）\n'
                                '    → 失準（橘）。⛔ 不換算、不猜匯率；數字只涵蓋台股那一批。"""\n'
                                '    _fx = tuple(getattr(result, "fx_excluded", ()) or ())\n'
                                '    if not _fx:\n'
                                '        return []\n'
                                '    return [(f"**{FX_PARTIAL_NOW}** —— {fx_excluded_text(_fx)}", FX_PARTIAL_WHERE)]\n',
                                ''),
                               ('        # XV-H3：有外幣未納入 → 總市值那一格改列客戶句（⛔ 不顯示部分總市值）。\n'
                                '        _fx_res = tuple(getattr(_res, "fx_excluded", ()) or ())\n'
                                '        _facts.insert(1, (_fx_facts(_fx_res)[0] if _fx_res else\n'
                                '                          ("納入計算的組合總市值（元）", f"{_res.total_value_twd:,.0f}")))\n',
                                '        _facts.insert(1, ("納入計算的組合總市值（元）",\n                          f"{_res.total_value_twd:,.0f}"))\n'),
                               ('    "兩套算法對不起來", "抓不到價格序列", "這個總額只涵蓋一部分持股",\n    "部分外幣資產未納入")      # XV-H3\n',
                                '    "兩套算法對不起來", "抓不到價格序列", "這個總額只涵蓋一部分持股")\n'),
                               ('    "確認上面那幾檔的代號與張數" + V2_EXCERPT_GAP + _V2_OLD_UI,\n'
                                '    NO_EXIT_MARKER + " —— 外幣資產的匯率來源、時點與成本幣別尚未定義")      # XV-H3\n',
                                '    "確認上面那幾檔的代號與張數" + V2_EXCERPT_GAP + _V2_OLD_UI)\n'),
                               ('       for _k in ("hold.alloc_split", "hold.deep.core_satellite")]\n'
                                '    # XV-H3（客戶 2026-10-28 裁示 A）：外幣／幣別未確認資產未納入（why 的代號清單在摺疊區原文）。\n'
                                '    + [_v2_rows_for(_k, FX_PARTIAL_NOW, (\n'
                                '           None, ("未納入：" + V2_EXCERPT_GAP + "｜原因：外幣資產，匯率與成本幣別未定義",\n'
                                '                  "未納入：" + V2_EXCERPT_GAP + "｜原因：幣別未確認"),\n'
                                '           NO_EXIT_MARKER + " —— 外幣資產的匯率來源、時點與成本幣別尚未定義"))\n',
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
    # `page_hold` 等由 NAV-1 節管的檔：`nav1_revert_for` 也先呼叫本節（d2／me_p1 的直接測試經它）。
    from tests.test_nav1_revert_chain import nav1_revert_for
    nv = inspect.getsource(nav1_revert_for)
    assert nv.index("xvext_revert_for(rel, code)") < nv.index("NAV1_REVERT_PAIRS.get(rel")
