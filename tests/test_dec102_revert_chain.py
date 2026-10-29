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

DEC102_BASE_SHA = {'shared/asset_currency_gate.py': '06362824a65587bc42bbe34cc8ed383b8a6eab2220692287d508bd230335d39a',
 'src/compute/notify/holdings_digest_message.py': '403da86c1ee43cb73cd3aa71f7a9672c03440a646bc8b993f5aaef5181c1b811',
 'src/services/dividend_station_service.py': '67fdaf7302ec377379fe357ea416fee1a30ed83840f378a3ff60533dd306d1ad',
 'src/ui/etf/etf_tab_dividend_station.py': '9554556c0ed8d1bd56ea0ce6feea04f61871c72f1e271fbc1c960714267445ee'}

DEC102_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'shared/asset_currency_gate.py': (('KEY_FX_UNCONFIRMED: str = "_fx_unconfirmed"\n'
                                    '\n'
                                    '#: DEC-102(3)（客戶 '
                                    '2026-10-28，XV-FX-ROW-ACTION＝同意）：外幣／幣別未確認的**持有個股列**，汰換燈結論\n'
                                    '#: 判得出（🟢 續抱）時**保留**原句，同列加註停利判不了（成本幣別未定義 ⇒ 損益% 不可判定）。\n'
                                    '#: ⛔ 不把整列換成 ⬜（燈號本身判得出）。明確外幣 → 前者；其餘（幣別未確認）→ 後者。\n'
                                    'FX_TP_UNJUDGED_FOREIGN: str = "停利未判：外幣"\n'
                                    'FX_TP_UNJUDGED_UNCONFIRMED: str = "停利未判：幣別未確認"\n'
                                    '\n'
                                    '\n'
                                    'def fx_take_profit_note(ticker) -> str:\n'
                                    '    """被排除代號的列層停利加註（同 `fx_exclusion_reason` 的兩分法，⛔ 不另立判定）。"""\n'
                                    '    return (FX_TP_UNJUDGED_FOREIGN if fx_exclusion_reason(ticker) == '
                                    'FX_EXCLUDED_REASON\n'
                                    '            else FX_TP_UNJUDGED_UNCONFIRMED)\n',
                                    'KEY_FX_UNCONFIRMED: str = "_fx_unconfirmed"\n'),),
 'src/compute/notify/holdings_digest_message.py': (('\n'
                                                    'def _vix_line(vix: "float | None", total: int, *, '
                                                    'data_short: bool = False) -> list[str]:\n'
                                                    '    """VIX 一行 + **一句白話該怎麼辦**（user '
                                                    '2026-08-24:「我也不知道該怎麼半」）。\n',
                                                    '\n'
                                                    'def _vix_line(vix: "float | None", total: int) -> '
                                                    'list[str]:\n'
                                                    '    """VIX 一行 + **一句白話該怎麼辦**（user '
                                                    '2026-08-24:「我也不知道該怎麼半」）。\n'),
                                                   ('    沒有數字卻給「照原計畫」等於憑空捏造一個「市場平靜」的結論。\n'
                                                    '\n'
                                                    '    ═══ DEC-102(1)（客戶 '
                                                    '2026-10-28，XV-LINE-VIX-LINE＝同意）：持股資料不足就不給行動句 ═══\n'
                                                    '    `data_short`（呼叫端以本檔 `_data_short(digest)` 判定，其謂詞是\n'
                                                    '    `digest_data_short(...) or digest.get("invalid")` '
                                                    '—— 與本檔續抱抑制同一謂詞，⛔ 不另造判定）為真時，只陳述 VIX 分級事實那一行，**不附**「→ '
                                                    '該怎麼做」那一行\n'
                                                    '    （missing ≠ HOLD；VIX 不得代替持股完整性判斷）。預設 False ＝ '
                                                    '修前輸出逐字不變。\n'
                                                    '    """\n',
                                                    '    沒有數字卻給「照原計畫」等於憑空捏造一個「市場平靜」的結論。\n    """\n'),
                                                   ('    }[_level]\n'
                                                    '    _fact = f"😱 VIX：{vix:.1f}\u3000'
                                                    '{LEVEL_EMOJI[_level]} {_label}\u3000有效判斷 {total} 檔"\n'
                                                    '    if data_short:\n'
                                                    '        return [_fact]      # DEC-102(1)：持股資料不足 → '
                                                    '只陳述分級事實，不附行動建議\n'
                                                    '    return [_fact, f"\u3000→ {_advice}"]\n'
                                                    '\n',
                                                    '    }[_level]\n'
                                                    '    return [f"😱 VIX：{vix:.1f}\u3000'
                                                    '{LEVEL_EMOJI[_level]} {_label}\u3000有效判斷 {total} 檔",\n'
                                                    '            f"\u3000→ {_advice}"]\n'
                                                    '\n'),
                                                   ('        f"🕐 {as_of}（開盤前檢視,價格以最近交易日收盤為準）",\n'
                                                    '        *_vix_line(_vix, _total, '
                                                    'data_short=_data_short(digest)),   # DEC-102(1)\n'
                                                    '        "",\n',
                                                    '        f"🕐 {as_of}（開盤前檢視,價格以最近交易日收盤為準）",\n'
                                                    '        *_vix_line(_vix, _total),\n'
                                                    '        "",\n')),
 'src/services/dividend_station_service.py': (('            _mark_insufficient(_row, ak=ak, held=held)\n'
                                               '            if (_row.get(FXG.KEY_FX_UNCONFIRMED) and ak == '
                                               'T.KIND_STOCK\n'
                                               '                    and not _row.get(SS.KEY_INSUFFICIENT) '
                                               'and _row.get("健檢") == "🟢"):\n'
                                               '                # DEC-102(3)（客戶 '
                                               '2026-10-28，XV-FX-ROW-ACTION＝同意）：外幣個股 🟢 續抱結論可證明 → 保留原句，\n'
                                               '                #   同列加註停利判不了（損益% 已因幣別未定義為 None）；⛔ 不換成 '
                                               '⬜。台股列不經此分支、逐字不變。\n'
                                               '                _row["建議動作"] = f"{_row.get(\'建議動作\', '
                                               '\'\')}\u3000{FXG.fx_take_profit_note(tk)}"\n'
                                               '            rows.append(_row)\n',
                                               '            _mark_insufficient(_row, ak=ak, held=held)\n'
                                               '            rows.append(_row)\n'),
                                              ('    "有標的資料不足或抓取失敗,列在『資料不足／無法判定』的標的請寫『資料不足／無法判定』,"\n'
                                               '    "其餘已列出的結論照原樣講,不得給組合層『全部續抱』類總結,也不得自行補上缺少的資料。"\n'
                                               '    # DEC-102(3)（QA M1，2026-10-28）：與 LINE 正文 '
                                               '`_vix_line(data_short=...)` 同一謂詞、同一原則 ——\n'
                                               '    #   持股資料不足時 VIX 只陳述分級事實，不得代替持股完整性給行動句。⑦ 與 LINE AI 總結共用本 '
                                               'prompt。\n'
                                               '    "\\nVIX 只可陳述分級事實，不得據以給任何行動建議（如照原計畫、定期定額）。")\n'
                                               '\n',
                                               '    "有標的資料不足或抓取失敗,列在『資料不足／無法判定』的標的請寫『資料不足／無法判定』,"\n'
                                               '    "其餘已列出的結論照原樣講,不得給組合層『全部續抱』類總結,也不得自行補上缺少的資料。")\n'
                                               '\n')),
 'src/ui/etf/etf_tab_dividend_station.py': (('from shared import dividend_station_thresholds as T\n'
                                             'from shared import asset_currency_gate as FXG  # '
                                             'DEC-102(2)：外幣原因句（L0 唯一來源）\n'
                                             'from shared import station_specs as SS\n',
                                             'from shared import dividend_station_thresholds as T\n'
                                             'from shared import station_specs as SS\n'),
                                            ('        compute_portfolio_totals,\n'
                                             '        fx_excluded_codes,\n'
                                             '    )\n',
                                             '        compute_portfolio_totals,\n    )\n'),
                                            ('        _held = [r for r in _rows if r.get("held")]\n'
                                             '        _fx = fx_excluded_codes(_rows)\n'
                                             '        if _fx:\n'
                                             '            # DEC-102(2)（DEC-019 '
                                             '凍結的客戶核准例外，XV-OLDUI-FX-REASON＝B）：外幣／幣別未確認 → L3 不算總額，\n'
                                             '            #   ⛔ 不講成「持股沒有張數／均價／現價」；改用新 UI 同一 L0 '
                                             '客戶句＋未納入清單（不新寫文案）。\n'
                                             '            _note = f"{FXG.FX_PARTIAL_TEXT}\u3000'
                                             '{FXG.fx_excluded_text(_fx)}"\n'
                                             '        elif not (_held and all((r.get("_detail") or '
                                             '{}).get("error") for r in _held)):\n'
                                             '            _note = ("未實現損益與總市值算不出來：持股沒有張數／均價／現價。"\n',
                                             '        _held = [r for r in _rows if r.get("held")]\n'
                                             '        if not (_held and all((r.get("_detail") or '
                                             '{}).get("error") for r in _held)):\n'
                                             '            _note = ("未實現損益與總市值算不出來：持股沒有張數／均價／現價。"\n'),
                                            ('    from src.services.dividend_station_service import (\n'
                                             '        compute_allocation_split, flag_take_profit, '
                                             'fx_excluded_codes)\n'
                                             '    _alloc = compute_allocation_split(rows)\n',
                                             '    from src.services.dividend_station_service import (\n'
                                             '        compute_allocation_split, flag_take_profit)\n'
                                             '    _alloc = compute_allocation_split(rows)\n'),
                                            ('        _held = [r for r in (rows or []) if r.get("held")]\n'
                                             '        _fx = fx_excluded_codes(rows)\n'
                                             '        if _fx:\n'
                                             '            # DEC-102(2)（DEC-019 '
                                             '凍結的客戶核准例外，XV-OLDUI-FX-REASON＝B）：同卡①，⛔ 不講成「未帶張數／均價」。\n'
                                             '            st.caption(f"📊 80/20 '
                                             '配置偏離：{FXG.FX_PARTIAL_TEXT}\u3000{FXG.fx_excluded_text(_fx)}")\n'
                                             '        elif _held and all((r.get("_detail") or '
                                             '{}).get("error") for r in _held):\n'
                                             '            st.caption("📊 80/20 配置偏離：無法計算實際佔比。"\n',
                                             '        _held = [r for r in (rows or []) if r.get("held")]\n'
                                             '        if _held and all((r.get("_detail") or {}).get("error") '
                                             'for r in _held):\n'
                                             '            st.caption("📊 80/20 配置偏離：無法計算實際佔比。"\n'))}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def dec102_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    # 📌 XV-ASOF 整合（DEC-102，2026-10-28；有意識的接鏈，⛔ 不是漏改）：XV-ASOF 批與本批同基底 `1e603094`、
    #   同動 `dividend_station_service.py` ⇒ 先換回 XV-ASOF 的改動（只套它自己的表、只套一次），
    #   本表與 `DEC102_BASE_SHA` ⛔ 一字未動；`base_module` 因此對兩批的檔都還原正確。
    from tests.test_asof_revert_chain import asof_only_revert
    code = asof_only_revert(rel, code)
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
