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
 'src/compute/notify/weekly_review_prompt.py': 'a9b0576369f177a6cc7a16657eadf54a505034d20fd05f22f40e0aba698987e3',
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
                              '#: 複驗 C MINOR-2：衛星（個股）缺現價時停利（損益%）判不了 ⇒「結論不受影響」不成立，改用這一句。\n'
                              'PRICE_MISSING_KEPT_SAT_TEXT: str = "缺現價（停利無法判定，其餘結論不受影響）"\n'
                              '#: 原因 → 給 ⑦ AI prompt／LINE 的事實短句（只講事實，不給結論）。\n'
                              'INSUFF_REASON_TEXT: dict = {\n'
                              '    INSUFF_ALL_UNJUDGED: "燈號全部判不出",\n'
                              '    INSUFF_NO_PRICE: "缺現價",\n'
                              '}\n',
                              ''),),
 'src/compute/notify/holdings_digest_message.py': (('import math\n', ''),
                                                   ('from shared import asset_currency_gate as FXG\n'
                                                    'from shared import holdings_data_short as HDS\n',
                                                    ''),
                                                   ('from shared import station_specs as SS\n', ''),
                                                   ('def _data_short(digest: dict) -> bool:\n'
                                                    '    """XV-H1-EXT（客戶 2026-10-28 裁示 A）：有抓取失敗或資料不足（燈全判不出／缺現價）的標的？\n'
                                                    '\n'
                                                    '    成立時正文**不印「續抱」**當缺資料的替代結論（missing ≠ HOLD；unavailable ≠ safe）。\n'
                                                    '    """\n'
                                                    '    # QA 回修 #2：持有列輸入／燈資料異常同樣是「判不出來」，不是「沒事」。\n'
                                                    '    # 複驗 C MAJOR-1/2：改用 L0 單一判定（與 ① gate、⑦ prompt 同一份）；`invalid` 仍額外看\n'
                                                    '    # （觀察清單列的燈異常也不該被講成「無紅燈」）。\n'
                                                    '    return HDS.digest_data_short(digest) or bool(digest.get("invalid"))\n'
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
                                                    '    _kept_sat = set(digest.get("price_missing_kept_satellite") or ())\n'
                                                    '    # 複驗 C MINOR-2：衛星（個股）缺現價 → 停利判不了，⛔ 不說「結論不受影響」。\n'
                                                    '    for _txt, _grp in ((SS.PRICE_MISSING_KEPT_TEXT, [c for c in _kept if c not in '
                                                    '_kept_sat]),\n'
                                                    '                       (SS.PRICE_MISSING_KEPT_SAT_TEXT, [c for c in _kept if c in '
                                                    '_kept_sat])):\n'
                                                    '        if _grp:\n'
                                                    '            _out.append(f"ℹ️ {_txt}：" + "、".join(str(_c) for _c in _grp))\n'
                                                    '    return _out\n'
                                                    '\n'
                                                    '\n'
                                                    'def _invalid_line(digest: dict) -> list[str]:\n'
                                                    '    """QA 回修 #2：資料異常未判的標的（與 ⑦ prompt「- 資料異常未判：」同一份 digest、同一種格式）。空 → 略過。"""\n'
                                                    '    _inv = digest.get("invalid") or []\n'
                                                    '    _out = (["⚠️ 資料異常未判：" + "、".join(\n'
                                                    '        f"{_code(d)}（" + "\u3000".join(f"{_l}：{_t}" for _l, _t in (d.get("項目") or '
                                                    '())) + "）"\n'
                                                    '        for d in _inv)] if _inv else [])\n'
                                                    '    # 複驗 C 第二輪 MINOR-A：契約漂移列（財報評等不在已知分級）同樣點名，讓收尾的「見上方清單」確有清單。\n'
                                                    '    if digest.get("contract_drift"):\n'
                                                    '        _out.append("⚠️ 資料異常未判（契約漂移）：" + "、".join(str(_c) for _c in '
                                                    'digest["contract_drift"]))\n'
                                                    '    return _out\n',
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
                                                   ('    if _total <= 0 and not digest.get("errors") and digest.get("contract_drift"):\n'
                                                    '        # 複驗 C 第二輪 MINOR-A：0 檔有效判斷、但原因不是抓取失敗（例：全是契約漂移）→ ⛔ 不寫「資料抓取全失敗」。\n'
                                                    '        lines += ["", "⚠️ 今日無任何持股完成評估（資料異常，見上方清單），未能判斷。"]\n'
                                                    '    elif _total <= 0:\n',
                                                    '    if _total <= 0:\n'),
                                                   ('    elif _no_action and _data_short(digest):\n'
                                                    '        # XV-H1-EXT（客戶 2026-10-28 裁示 A）：部分抓取失敗／燈全判不出／缺現價 → ⛔ 不印「續抱」\n'
                                                    '        # 當缺資料的替代結論；只講判得出的範圍，並把資料不足的標的指回上方清單。\n'
                                                    '        # 複驗 C MINOR-2：只講實際存在的那幾種（只有缺現價保留結論／外幣時，⛔ 不寫「資料不足…未下結論」）。\n'
                                                    '        _why = [_t for _t, _on in (\n'
                                                    '            ("資料不足或抓取失敗的標的未下結論",\n'
                                                    '             bool(digest.get("errors") or digest.get("insufficient") or '
                                                    'digest.get("invalid")\n'
                                                    '                  or digest.get("contract_drift") or not '
                                                    'HDS.total_judged(digest.get("total")))),\n'
                                                    '            ("部分持股缺現價", bool(digest.get("price_missing_kept"))),\n'
                                                    '            ("部分持股為外幣／幣別未確認", bool(digest.get("fx_excluded")))) if _on]\n'
                                                    '        lines += ["", "📭 判得出的標的今日無換出／加碼／停利訊號；"\n'
                                                    '                      + "、".join(_why or ["部分持股資料不足"]) + "（見上方清單），不給組合層總結。"]\n',
                                                    '')),
 'src/compute/notify/weekly_review_prompt.py': (('    _prompt = f"""你是台股資料整理助手。下面 <Macro> 是本週大盤定調、<Holdings> 是使用者持股\\\n',
                                                 '    return f"""你是台股資料整理助手。下面 <Macro> 是本週大盤定調、<Holdings> 是使用者持股\\\n'),
                                                ('    # 複驗 C MAJOR-3（XV-H1-EXT 同一原則：missing ≠ HOLD，比照 ⑦ `build_summary_prompt`）：\n'
                                                 '    # 有燈號 ⚪（判不出）的列時，「資料不足 → 留意即可」改為要求寫「資料不足／無法判定」，並加約束\n'
                                                 '    # （不得給組合層 blanket 總結、不得補資料）。資料完整時 prompt 逐字不變。\n'
                                                 '    if any(str((_r or {}).get("燈號", "")).startswith("⚪") for _r in (holding_rows or '
                                                 '[])):\n'
                                                 '        _prompt = _prompt.replace(\n'
                                                 '            "資料不足 → 留意即可）",\n'
                                                 '            "資料不足／判不出 → 寫「資料不足／無法判定」）").replace(\n'
                                                 '            "3. 全程繁體中文,白話簡短;逐檔理由**一句話**,務必引用資料事實,不要自己編數字。\\n",\n'
                                                 '            "3. 全程繁體中文,白話簡短;逐檔理由**一句話**,務必引用資料事實,不要自己編數字。\\n"\n'
                                                 '            "4. <Holdings> 有標的資料不足或判不出:該標的請寫『資料不足／無法判定』,"\n'
                                                 '            "不得給組合層『全部續抱』『均無落後』類總結,也不得自行補上缺少的資料。\\n")\n'
                                                 '    return _prompt\n',
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
 'src/services/dividend_station_service.py': (('from shared import asset_currency_gate as FXG\n'
                                               'from shared import holdings_data_short as HDS\n',
                                               ''),
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
                                               '    # 複驗 C MINOR-1：個股 ⚪ 若是**契約漂移**（grade 不在已知分級，L2 `assess_stock` 明定 ⛔ 不得畫成\n'
                                               '    # 「資料不足」）→ 保留 L2 原診斷句「⚪ 財報評等「Z」不在已知分級內（上游契約漂移,請回報）…」，\n'
                                               '    # ⛔ 不換成 ⬜；它仍由 L0 `holdings_data_short.row_data_short` 計入組合層資料不足。\n'
                                               '    # 只有「沒有輸入」的 ⚪ 才換 ⬜。\n'
                                               '    # ⚠️ 揭露：本函式改的是 L3 列的 `建議動作` 文字 —— 舊 UI 存股戰情室（`src/ui/etf/etf_tab_dividend_station`）\n'
                                               '    #   與新 UI 共用 `get_station_rows`，故舊 UI 的這一欄同樣會顯示 ⬜ 句。屬 missing ≠ HOLD 之修正，舊 UI 檔未改。\n'
                                               '    if _is_stock and _unjudged and row.get("_miss_reason") == SS.MISS_CONTRACT_DRIFT:\n'
                                               '        _unjudged = False\n'
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
                                              ('    drift: list[str] = []\n', ''),
                                              ('            continue\n'
                                               '        if HDS.is_contract_drift(r):\n'
                                               '            # 複驗 C 第二輪 MINOR-A：契約漂移列判不出 ⇒ ⛔ 不算進「有效判斷檔數」，另列事實。\n'
                                               '            drift.append(str(r.get("代號", "")))\n',
                                               ''),
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
                                               '        # 複驗 C MINOR-2：其中的衛星（個股）—— 停利判不了（只有非空才有這一鍵）。\n'
                                               '        _kept_sat = [str(r.get("代號", "")) for r in (rows or [])\n'
                                               '                     if not r.get("_detail", {}).get("error") and '
                                               'r.get(SS.KEY_PRICE_MISSING_KEPT)\n'
                                               '                     and r.get("種類") == "個股"]\n'
                                               '        if _kept_sat:\n'
                                               '            _out["price_missing_kept_satellite"] = _kept_sat\n'
                                               '    # XV-H3：幣別未確認、未納入總額／比例的持有列（只有非空才有這一鍵；`allocation` 此時為 None）。\n'
                                               '    _fx = fx_excluded_codes(rows)\n'
                                               '    if _fx:\n'
                                               '        _out["fx_excluded"] = _fx\n'
                                               '    # 複驗 C MAJOR-1/2：組合層「資料不足」的單一判定（L0 `holdings_data_short.row_data_short`）\n'
                                               '    # → 代號清單（只有非空才有這一鍵）。⑦ prompt 與 LINE 一律以 `digest_data_short()` 讀它。\n'
                                               '    _short = list(dict.fromkeys(str(r.get("代號", "")) for r in (rows or []) if '
                                               'HDS.row_data_short(r)))\n'
                                               '    if _short:\n'
                                               '        _out["data_short"] = _short\n'
                                               '    if drift:                          # 複驗 C 第二輪 MINOR-A（只有非空才有這一鍵）\n'
                                               '        _out["contract_drift"] = drift\n',
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
                                               '    # 複驗 C MAJOR-1/2：與 ①／LINE 同一份判定（L0 `holdings_data_short.digest_data_short`）。\n'
                                               '    _short = HDS.digest_data_short(digest)\n'
                                               '    _guide = (_INSUFFICIENT_INSTRUCTION if _short\n'
                                               '              else "" if _inv else "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。")\n',
                                               ''),
                                              ('        + _guide + "\\n"\n',
                                               '        + ("" if (_inv or _no_judged) else "沒有紅燈也沒有加碼時,請明講『續抱、定期定額即可』。") + "\\n"\n'),
                                              ('    if digest.get("contract_drift"):\n'
                                               '        # 複驗 C 第二輪 MINOR-A：契約漂移列（保留原診斷句、不換 ⬜）在事實裡點名。\n'
                                               '        _base += f"- 資料異常未判（契約漂移）：{\'、\'.join(str(_c) for _c in '
                                               'digest[\'contract_drift\'])}\\n"\n'
                                               '    for _lbl, _grp in (("持有", [d for d in _ins if d.get("held", True)]),\n'
                                               '                       ("觀察清單", [d for d in _ins if not d.get("held", True)])):\n'
                                               '        if _grp:\n'
                                               '            _base += (f"- 資料不足／無法判定（{_lbl}）："\n'
                                               '                      + "、".join(f"{d[\'代號\']}（" + "、".join(SS.INSUFF_REASON_TEXT.get(_r, '
                                               'str(_r))\n'
                                               '                                                             for _r in d.get("原因", ())) + '
                                               '"）"\n'
                                               '                                 for d in _grp) + "\\n")\n'
                                               '    _kept_sat = set(digest.get("price_missing_kept_satellite") or ())\n'
                                               '    for _txt, _grp in ((SS.PRICE_MISSING_KEPT_TEXT, [c for c in _kept if c not in '
                                               '_kept_sat]),\n'
                                               '                       (SS.PRICE_MISSING_KEPT_SAT_TEXT, [c for c in _kept if c in '
                                               '_kept_sat])):\n'
                                               '        if _grp:\n'
                                               '            _base += f"- {_txt}：{\'、\'.join(str(_c) for _c in _grp)}\\n"\n'
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
                                            ('def _held_n(rows, *, twd_only: bool = False) -> int:\n'
                                             '    """有幾列是「持有」（含算不出金額的）—— 給畫面講 `valued/held`。\n'
                                             '\n'
                                             '    `twd_only=True`（XV-H3 QA 回修 #5；壓測／VaR 用）：外幣／幣別未確認的列**不計**（它們已另列在\n'
                                             '    `fx_excluded`）⇒ `valued/held` 與 `coverage_pct` 講的是同一批台股列，⛔ 不再把外幣算成「缺張數／均價／現價」。\n'
                                             '    配息現金流維持預設（它有自己的海外排除與 `lots_n/held_n`）。\n'
                                             '    """\n',
                                             'def _held_n(rows) -> int:\n    """有幾列是「持有」（含算不出金額的）—— 給畫面講 `valued/held`。"""\n'),
                                            ('               if isinstance(_r, dict) and _r.get("held") and not _row_failed(_r)\n'
                                             '               and not (twd_only and _is_fx_unconfirmed(_r)))\n',
                                             '               if isinstance(_r, dict) and _r.get("held") and not _row_failed(_r))\n'),
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
                                            ('    _priced = priced_rows(rows)\n'
                                             '    _held = _held_n(rows, twd_only=True)\n'
                                             '    if not _priced:\n',
                                             '    _priced = priced_rows(rows)\n    _held = _held_n(rows)\n    if not _priced:\n'),
                                            ('        return StressResult(reason=(FXG.FX_ONLY_REASON if (not _held and '
                                             '_fx_excluded(rows))\n'
                                             '                                    else REASON_NO_PRICED_ROWS), drop_pct=_drop,\n',
                                             '        return StressResult(reason=REASON_NO_PRICED_ROWS, drop_pct=_drop,\n'),
                                            ('    #: XV-H3（加性）：同 `StressResult.fx_excluded`。\n'
                                             '    fx_excluded: tuple[str, ...] = field(default=(), repr=False, compare=False)\n',
                                             ''),
                                            ('\n@_attach_fx\ndef get_portfolio_var(rows, *, strict: bool = False) -> VarResult:\n',
                                             '\ndef get_portfolio_var(rows, *, strict: bool = False) -> VarResult:\n'),
                                            ('    _priced = priced_rows(rows)\n'
                                             '    _held = _held_n(rows, twd_only=True)\n'
                                             '    _min_days = int(TRADING_DAYS_PER_MONTH)\n',
                                             '    _priced = priced_rows(rows)\n'
                                             '    _held = _held_n(rows)\n'
                                             '    _min_days = int(TRADING_DAYS_PER_MONTH)\n'),
                                            ('        return VarResult(reason=(FXG.FX_ONLY_REASON if (not _held and _fx_excluded(rows))\n'
                                             '                                 else REASON_NO_PRICED_ROWS), **_base)\n',
                                             '        return VarResult(reason=REASON_NO_PRICED_ROWS, **_base)\n'),
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
                                '    FX_ONLY_REASON,\n'
                                '    FX_PARTIAL_TEXT,\n'
                                '    KEY_FX_UNCONFIRMED,\n'
                                '    fx_excluded_text,\n'
                                ')\n',
                                ''),
                               ('        # XV-H1-EXT QA 回修 #1（BLOCKER）：燈全判得出、但資料不足（建議動作被換成 ⬜）或資料異常的列\n'
                                '        # 同樣「判不全」⇒ 計入「未判 N」，且 ⛔ 不准印巡航／沒事句。\n'
                                '        _short = _short_data_flags(_rows)\n'
                                '        _unjudged = sum(1 for _c, _sh in zip(_cells, _short) if _sh or not is_fully_judged(_c))\n',
                                '        _unjudged = sum(1 for _c in _cells if not is_fully_judged(_c))\n'),
                               ('        _cruise = (cruise_or_gap(_judged, _total, all_rows_judged=_all_judged) if not any(_short)\n'
                                '                   else _short_data_text(_rows))\n',
                                '        _cruise = cruise_or_gap(_judged, _total, all_rows_judged=_all_judged)\n'),
                               ('\n'
                                '\n'
                                '#: XV-H1-EXT QA 回修 #1：① 有資料不足／資料異常的列時取代巡航句（語彙沿用 L0「資料不足／無法判定」\n'
                                '#: 與 L4 `cruise_or_gap` 的「不是都沒事,是沒東西可以判」）。\n'
                                '#: 複驗 C：~~"資料不足／無法判定或資料異常 —— …"~~ → 判定改走 L0 單一判定後，涵蓋缺現價（保留結論）與外幣，故補字。\n'
                                '#: 📌 複驗 C 第二輪 MINOR-B（有意識的變更，⛔ 不是漏刪）：~~本常數整句當 ① 替代句~~ → 改由\n'
                                '#:    `_short_data_text()` 依實際原因組（燈全判得出、只有外幣時不得說「沒東西可以判」）。本常數保留給其頭尾。\n'
                                'SHORT_DATA_GAP_TEXT: str = "資料不足／無法判定、資料異常、缺現價或幣別未確認 —— **不是都沒事,是沒東西可以判**"\n'
                                '#: 只有缺現價（保留結論）／外幣時的尾句（不是「沒東西可以判」—— 燈都判得出，只是組合層總結不完整）。\n'
                                'SHORT_DATA_PARTIAL_TAIL: str = "無法完整判定 —— 組合層不下結論"\n'
                                '\n'
                                '\n'
                                'def _short_data_text(rows: Sequence[Mapping[str, Any]]) -> str:\n'
                                '    """複驗 C 第二輪 MINOR-B：① 替代句依 L0 `row_short_kind` 的實際原因組（比照 LINE 收尾 `_why`）。\n'
                                '\n'
                                '    例：只有外幣 →「部分持股為外幣／幣別未確認，總市值／配置與停利無法完整判定 —— 組合層不下結論」；\n'
                                '    有判不出的列 →「N 檔資料不足／無法判定或資料異常 —— **不是都沒事,是沒東西可以判**」（可再接其他原因）。\n'
                                '    """\n'
                                '    from shared.holdings_data_short import SHORT_FX, SHORT_PRICE, SHORT_UNJUDGED, row_short_kind\n'
                                '    _kinds = [row_short_kind(dict(_r)) for _r in rows]\n'
                                '    _n_un = sum(1 for _k in _kinds if _k == SHORT_UNJUDGED)\n'
                                '    _price, _fx = SHORT_PRICE in _kinds, SHORT_FX in _kinds\n'
                                '    _parts = ([f"{_n_un} 檔資料不足／無法判定或資料異常"] if _n_un else []) \\\n'
                                '        + (["部分持股缺現價"] if _price else []) + (["部分持股為外幣／幣別未確認"] if _fx else [])\n'
                                '    if _n_un:\n'
                                '        return "、".join(_parts) + " —— **不是都沒事,是沒東西可以判**"\n'
                                '    return ("、".join(_parts) + "，" + ("總市值／配置與停利" if _fx else "停利")\n'
                                '            + SHORT_DATA_PARTIAL_TAIL)\n'
                                '\n'
                                '\n'
                                'def _short_data_flags(rows: Sequence[Mapping[str, Any]]) -> list[bool]:\n'
                                '    """逐列：是否讓組合層「資料不足」。複驗 C MAJOR-1/2：⛔ 本頁不再自己判 —— 一律走 L0\n'
                                '    `holdings_data_short.row_data_short`（與 ⑦ prompt、LINE 正文同一份；含缺現價保留結論、\n'
                                '    外幣／幣別未確認、契約漂移）。"""\n'
                                '    from shared.holdings_data_short import row_data_short\n'
                                '    return [row_data_short(dict(_r)) for _r in rows]\n',
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
                               ('                       f"{station.unjudged_rows} 列不是「每一盞適用燈都判得出來」"\n'
                                '                       # XV-H1-EXT QA 回修 #1：資料不足／資料異常的列同樣算進來。\n'
                                '                       + ("（含資料不足／無法判定、資料異常、缺現價或幣別未確認的列）"\n'
                                '                          if any(_short_data_flags(station.rows))\n'
                                '                          else "")\n'
                                '                       + "—— 只要有一列不滿足，就不准說「今天沒事」"))\n',
                                '                       f"{station.unjudged_rows} 列不是「每一盞適用燈都判得出來」—— "\n'
                                '                       "只要有一列不滿足，就不准說「今天沒事」"))\n'),
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
                               ('    # XV-H3 QA 回修 #10：持有衛星是外幣／幣別未確認 → L3 把損益% 設 None（成本幣別未定義）→\n'
                                '    # 同樣沒被判過，⛔ 不落到「沒有任何一檔達門檻（有效結果）」。只有這一種時走「不適用 · 重跑無效」。\n'
                                '    _fx_tp = tuple(_c for _c in _fx_codes(station.rows)\n'
                                '                   if any(str(_r.get("代號", "")) == _c and _r.get("種類") == "個股"\n'
                                '                          for _r in station.rows))\n'
                                '    _fail_unjudged = bool(_unjudged)      # 取數失敗／資料異常那幾種（升紅）\n'
                                '    _unjudged = _unjudged + _fx_tp\n',
                                ''),
                               ('        reason=(MISS_FETCH_FAILED if _fail_unjudged\n'
                                '                else MISS_NOT_APPLICABLE if _fx_tp else ""))\n',
                                '        reason=MISS_FETCH_FAILED if _unjudged else "")\n'),
                               ('        if _fx_tp:                              # XV-H3 QA #10：外幣那幾檔同樣判不了\n'
                                '            _why += f"；{fx_excluded_text(_fx_tp)}"\n',
                                ''),
                               ('    elif _fx_tp:\n'
                                '        # XV-H3 QA 回修 #10：只有外幣／幣別未確認的衛星判不了（沒有取數失敗）。\n'
                                '        _note = Note(now=TP_FAILED_NOW, why=fx_excluded_text(_fx_tp), where=FX_PARTIAL_WHERE)\n',
                                ''),
                               ('    _held = getattr(result, "held_n", None)\n'
                                '    _fx = tuple(getattr(result, "fx_excluded", ()) or ())\n'
                                '    if coverage and isinstance(_valued, int) and isinstance(_held, int) and _held:\n',
                                '    _held = getattr(result, "held_n", None)\n'
                                '    if coverage and isinstance(_valued, int) and isinstance(_held, int) and _held:\n'),
                               ('        # XV-H3 QA 回修 #5：有外幣排除時 L3 的 `held_n` 只數台股列 ⇒ 標明「台股」，外幣另列原因\n        # （⛔ 不把外幣講成「缺張數／均價／現價」）。\n',
                                ''),
                               ('                       f"{_held} 檔{\'台股\' if _fx else \'\'}持有列裡納入了 {_valued} 檔"\n',
                                '                       f"{_held} 檔持有列裡納入了 {_valued} 檔"\n'),
                               ('                          if _valued < _held else "")\n'
                                '                       + (f"；另外 {fx_excluded_text(_fx)} —— **不進分子也不進分母**" if _fx else "")))\n',
                                '                          if _valued < _held else "")))\n'),
                               ('    _bits += _fx_degraded_bits(result)\n', ''),
                               ('\n'
                                '\n'
                                'def _fx_value_label(result: Any) -> str:\n'
                                '    """失準卡的「現值」列標籤。XV-H3 QA 回修 #5：有外幣排除時標明只涵蓋台股（⛔ 不稱「總市值」）。"""\n'
                                '    if getattr(result, "fx_excluded", ()):\n'
                                '        return "現值（僅已納入台股部分，已失準，別照門檻讀）"\n'
                                '    return "現值（已失準，別照門檻讀）"\n'
                                '\n'
                                '\n'
                                'def _fx_only(result: Any) -> bool:\n'
                                '    """XV-H3 QA 回修 #5：L3 回報持有列全是外幣／幣別未確認（台股一檔都沒有）。"""\n'
                                '    return getattr(result, "reason", "") == FX_ONLY_REASON\n'
                                '\n'
                                '\n'
                                'def _fx_degraded_bits(result: Any) -> list[tuple[str, str]]:\n'
                                '    """XV-H3（客戶 2026-10-28 裁示 A）：L3 回報有外幣／幣別未確認的持有列沒進這個數字（`fx_excluded`）\n'
                                '    → 失準（橘）。⛔ 不換算、不猜匯率；數字只涵蓋台股那一批。"""\n'
                                '    _fx = tuple(getattr(result, "fx_excluded", ()) or ())\n'
                                '    if not _fx:\n'
                                '        return []\n'
                                '    return [(f"**{FX_PARTIAL_NOW}** —— {fx_excluded_text(_fx)}", FX_PARTIAL_WHERE)]\n',
                                ''),
                               ('        # XV-H3 QA 回修 #5：持有列全是外幣 → 「不適用 · 重跑無效」（⛔ 不是「有效的結果，去補張數」）。\n'
                                '        reason=(MISS_FETCH_FAILED if _stress_skipped\n'
                                '                else MISS_NOT_APPLICABLE if _fx_only(_res) else ""),\n',
                                '        reason=MISS_FETCH_FAILED if _stress_skipped else "",\n'),
                               ('        # XV-H3：有外幣未納入 → 總市值那一格改列客戶句（⛔ 不顯示部分總市值）。\n'
                                '        _fx_res = tuple(getattr(_res, "fx_excluded", ()) or ())\n'
                                '        _facts.insert(1, (_fx_facts(_fx_res)[0] if _fx_res else\n'
                                '                          ("納入計算的組合總市值（元）", f"{_res.total_value_twd:,.0f}")))\n',
                                '        _facts.insert(1, ("納入計算的組合總市值（元）",\n                          f"{_res.total_value_twd:,.0f}"))\n'),
                               ('                          # 複驗 C MINOR-3：外幣排除時分母只是台股那一批 ⇒ ⛔ 不稱「總市值」。\n'
                                '                          f"回撤大於{\'已納入台股部分市值\' if _fx_res else \'總市值\'}的 "\n'
                                '                          f"{_res.warn_pct:g} 個百分點就示警"))\n',
                                '                          f"回撤大於總市值的 {_res.warn_pct:g} 個百分點就示警"))\n'),
                               ('        # 一邊掛「🟠 門檻已失準」一邊出「門檻內」是同一張卡說兩句相反的話。\n'
                                '        _facts.insert(0, (_fx_value_label(_res), _shown))\n'
                                '        return (Card(key="hold.deep.stress", label="壓力測試",\n',
                                '        # 一邊掛「🟠 門檻已失準」一邊出「門檻內」是同一張卡說兩句相反的話。\n'
                                '        _facts.insert(0, ("現值（已失準，別照門檻讀）", _shown))\n'
                                '        return (Card(key="hold.deep.stress", label="壓力測試",\n'),
                               ('    elif _fx_only(_res):\n'
                                '        _note = Note(now=FX_PARTIAL_NOW, why=fx_excluded_text(_res.fx_excluded),\n'
                                '                     where=FX_PARTIAL_WHERE)\n',
                                ''),
                               ('        reason=(MISS_FETCH_FAILED if _var_skipped\n'
                                '                else MISS_NOT_APPLICABLE if _fx_only(_res) else ""),   # XV-H3 QA #5\n',
                                '        reason=MISS_FETCH_FAILED if _var_skipped else "",\n'),
                               ('        # ~~"日報酬是**原幣別**報酬；外幣計價的持股未含匯率變動"~~ ← XV-H3 QA 回修 #5（有意識的更正）：\n'
                                '        #   外幣／幣別未確認的持股自 XV-H3 起**不納入**本格（不是納入但未含匯率）。\n'
                                '        ("已知限制", "外幣／幣別未確認的持股**不納入**本格（匯率與成本幣別未定義，不換算）"),\n',
                                '        ("已知限制", "日報酬是**原幣別**報酬；外幣計價的持股未含匯率變動"),\n'),
                               ('                          + (f"，占已納入台股部分市值 {_res.monthly_99_pct:.2f}%"\n'
                                '                             if getattr(_res, "fx_excluded", ()) else\n'
                                '                             f"，占總市值 {_res.monthly_99_pct:.2f}%")\n'
                                '                          + f"（示警門檻 {_res.warn_pct:g}）"))\n',
                                '                          f"，占總市值 {_res.monthly_99_pct:.2f}%"\n'
                                '                          f"（示警門檻 {_res.warn_pct:g}）"))\n'),
                               ('        # 燈號頻道留白：門檻已失準卻還出「月度尾部可控」，是同一張卡說兩句相反的話。\n'
                                '        _facts.insert(0, (_fx_value_label(_res), _shown))\n'
                                '        return (Card(key="hold.deep.var", label="VaR（風險值）",\n',
                                '        # 燈號頻道留白：門檻已失準卻還出「月度尾部可控」，是同一張卡說兩句相反的話。\n'
                                '        _facts.insert(0, ("現值（已失準，別照門檻讀）", _shown))\n'
                                '        return (Card(key="hold.deep.var", label="VaR（風險值）",\n'),
                               ('    elif _fx_only(_res):\n'
                                '        # XV-H3 QA 回修 #5：持有列全是外幣 → 外幣原因，⛔ 不叫人補張數／均價。\n'
                                '        _note = Note(now=FX_PARTIAL_NOW, why=fx_excluded_text(_res.fx_excluded),\n'
                                '                     where=FX_PARTIAL_WHERE)\n',
                                ''),
                               ('    "兩套算法對不起來", "抓不到價格序列", "這個總額只涵蓋一部分持股",\n    "部分外幣資產未納入")      # XV-H3\n',
                                '    "兩套算法對不起來", "抓不到價格序列", "這個總額只涵蓋一部分持股")\n'),
                               ('    "確認上面那幾檔的代號與張數" + V2_EXCERPT_GAP + _V2_OLD_UI,\n'
                                '    NO_EXIT_MARKER + " —— 外幣資產的匯率來源、時點與成本幣別尚未定義")      # XV-H3\n',
                                '    "確認上面那幾檔的代號與張數" + V2_EXCERPT_GAP + _V2_OLD_UI)\n'),
                               ('    # XV-H3（客戶 2026-10-28 裁示 A）：外幣／幣別未確認資產未納入（why 的代號清單在摺疊區原文）。\n'
                                '    + [_v2_rows_for(_k, FX_PARTIAL_NOW, (\n'
                                '           None, ("未納入：" + V2_EXCERPT_GAP + "｜原因：外幣資產，匯率與成本幣別未定義",\n'
                                '                  "未納入：" + V2_EXCERPT_GAP + "｜原因：幣別未確認"),\n'
                                '           NO_EXIT_MARKER + " —— 外幣資產的匯率來源、時點與成本幣別尚未定義"))\n'
                                '       for _k in ("hold.alloc_split", "hold.deep.core_satellite",\n'
                                '                  "hold.deep.stress", "hold.deep.var")]       # QA #5：壓測／VaR 全外幣\n',
                                ''),
                               ('                  *_V2_INVALID_WHY,\n'
                                '                  # XV-H3 QA #10：只有外幣／幣別未確認的衛星判不了。\n'
                                '                  "未納入：" + V2_EXCERPT_GAP + "｜原因：外幣資產，匯率與成本幣別未定義",\n'
                                '                  "未納入：" + V2_EXCERPT_GAP + "｜原因：幣別未確認"),\n'
                                '           (_V2_NO_EXIT_REPORT, _V2_CHECK_NET,\n'
                                '            NO_EXIT_MARKER + " —— 外幣資產的匯率來源、時點與成本幣別尚未定義"))),\n',
                                '                  *_V2_INVALID_WHY),\n           (_V2_NO_EXIT_REPORT, _V2_CHECK_NET))),\n'))}



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
