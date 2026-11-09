"""tests/test_b2_consumer_revert_chain.py — D3 B2(空抓取三態消費端一致性,DEC-148)對
`src/data/macro/macro_cache_reader.py`／`src/ui/views/_market_blocks.py` 的還原鏈新頭節。

═══ 為什麼需要 ═══════════════════════════════════════════════════════════
B2 在 `macro_cache_reader.compute_cache_staleness`／`_attach_staleness` 加了 upstream_state／fetch_outcome／fetch_evidence,
並在 `_market_blocks.basis_chart_a` 把「上游最後一次錯誤」文案依三態分流。這兩個檔被舊鏈(Z40／Z63／C1／D2 守衛;P4／UIM…)
以「新寫法 → 舊寫法」錨點還原成各自的基底 sha256;B2 的新增行落在它們的比對範圍之內 ⇒ 需在鏈頭**往前接一節**,
先把 B2 換回(比照 `d3_revert_for` 接在 `p4_revert_for` 開頭的作法;⛔ 不動任何舊表與舊基底 sha、不放寬任何斷言、不 skip)。

基底 ＝ B2 開工前的 `bda43f3`(origin/main);`git show bda43f3:<檔> | sha256sum` 實算後寫死,測試不依賴 git。
還原組由 difflib 逐區塊自動產生(每個 new 片段在現行檔恰 1 次、在基底 0 次)。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

B2_BASE_SHA = {'src/data/macro/macro_cache_reader.py': '7ab05a3a445691c2c3615dd4e2c3565d160d5619fe5b9c393c3cd4d36e737583',
 'src/ui/views/_market_blocks.py': '6c00495231505f34dc9c61c6007578b68d41285191db32d2941c4266a3b37da0'}

B2_REVERT_PAIRS = {'src/data/macro/macro_cache_reader.py': (('          "upstream_error": str | None,  # metadata '
                                           '自陳的 `last_error`\n'
                                           '          "upstream_state": str,         # B2:上游抓取狀態 '
                                           '"" / NO_NEW_DATA / FETCH_FAILED / UNDETERMINED\n'
                                           '          "fetch_outcome":  str | None,  # B2:metadata '
                                           '原樣的 `fetch_outcome`(舊 metadata 無此欄 → None)\n'
                                           '          "fetch_evidence": str,         # B2:metadata '
                                           '原樣的 `fetch_evidence`(已洗過;沒有 → "")\n'
                                           '          "meta_last_updated": str | None,\n',
                                           '          "upstream_error": str | None,  # metadata '
                                           '自陳的 `last_error`\n'
                                           '          "meta_last_updated": str | None,\n'),
                                          ('           "age_days": None, "periods_behind": None,\n'
                                           '           "upstream_error": None, '
                                           '"meta_last_updated": None,\n'
                                           '           "upstream_state": "", "fetch_outcome": '
                                           'None, "fetch_evidence": ""}\n'
                                           '\n',
                                           '           "age_days": None, "periods_behind": None,\n'
                                           '           "upstream_error": None, '
                                           '"meta_last_updated": None}\n'
                                           '\n'),
                                          ('    out["meta_last_updated"] = '
                                           '_entry.get("last_updated")\n'
                                           '    # B2(DEC-148):三態折成「上游狀態」由 L0 '
                                           '`shared.upstream_state` '
                                           '統一判定(last_error／fetch_outcome／freshness 三者各自\n'
                                           '    # 表達自己的語意、不互相取代;本欄只描述「最近一次抓取」,⛔ 不蘊含資料新鮮,也不改 '
                                           'as_of／is_stale)。\n'
                                           '    # 舊 metadata 缺 fetch_outcome → 純標記字串視為 '
                                           'UNDETERMINED(不預設成功)。\n'
                                           '    from shared.fetch_outcome import '
                                           'META_EVIDENCE_KEY, META_OUTCOME_KEY\n'
                                           '    from shared.upstream_state import '
                                           'classify_upstream, upstream_state_value\n'
                                           '    out["fetch_outcome"] = '
                                           '_entry.get(META_OUTCOME_KEY)\n'
                                           '    _state, _ev = '
                                           'classify_upstream(out["upstream_error"], '
                                           'out["fetch_outcome"], _entry.get(META_EVIDENCE_KEY))\n'
                                           '    out["upstream_state"] = '
                                           'upstream_state_value(_state)\n'
                                           '    out["fetch_evidence"] = _ev\n'
                                           '\n',
                                           '    out["meta_last_updated"] = '
                                           '_entry.get("last_updated")\n'
                                           '\n'),
                                          ('        series.attrs["upstream_error"] = '
                                           '_st["upstream_error"]\n'
                                           '        if _st["upstream_state"]:          # '
                                           'B2:只在有上游問題時才加(無問題時 attrs 形狀與 B2 前逐字相同)\n'
                                           '            series.attrs["upstream_state"] = '
                                           '_st["upstream_state"]\n'
                                           '            if _st["fetch_evidence"]:\n'
                                           '                series.attrs["fetch_evidence"] = '
                                           '_st["fetch_evidence"]\n'
                                           '    except Exception:  # noqa: BLE001 — 極舊 pandas 無 '
                                           '.attrs;不影響資料本身\n',
                                           '        series.attrs["upstream_error"] = '
                                           '_st["upstream_error"]\n'
                                           '    except Exception:  # noqa: BLE001 — 極舊 pandas 無 '
                                           '.attrs;不影響資料本身\n'),
                                          ('              + '
                                           '(f";metadata.last_error={_st[\'upstream_error\']!r}"\n'
                                           '                 f";上游狀態={_st[\'upstream_state\'] or '
                                           '\'—\'}"\n'
                                           '                 + (f"({_st[\'fetch_evidence\']})" if '
                                           '_st["fetch_evidence"] else "")\n'
                                           '                 if _st["upstream_error"] else ""))\n',
                                           '              + '
                                           '(f";metadata.last_error={_st[\'upstream_error\']!r}"\n'
                                           '                 if _st["upstream_error"] else '
                                           '""))\n')),
 'src/ui/views/_market_blocks.py': (('from shared.ui_state import UI_DEGRADED, UI_EMPTY, '
                                     'UI_FAILED, UI_LIVE\n'
                                     'from shared.upstream_state import classify_upstream, '
                                     'is_empty_fetch_marker, upstream_state_text, '
                                     'upstream_state_value\n'
                                     'from src.services import market_twii_view_service as '
                                     'twii_svc\n',
                                     'from shared.ui_state import UI_DEGRADED, UI_EMPTY, '
                                     'UI_FAILED, UI_LIVE\n'
                                     'from src.services import market_twii_view_service as '
                                     'twii_svc\n'),
                                    ('        _miss.insert(0, f"指數線：{scrub_secrets(view.error)}")\n'
                                     '    _vstate = getattr(view, "upstream_state", "") if view is '
                                     'not None else ""\n'
                                     '    if view is not None and view.ok and (view.upstream_error '
                                     'or _vstate):\n'
                                     '        # B2（DEC-148）：三態分流文案。⛔ '
                                     '不再把所有空抓取（「抓取結果為空」）都寫成「上游最後一次錯誤」。\n'
                                     '        _up = _vstate or '
                                     'upstream_state_value(classify_upstream(view.upstream_error)[0])\n'
                                     '        if _up == "FETCH_FAILED" and view.upstream_error and '
                                     'not is_empty_fetch_marker(view.upstream_error):\n'
                                     '            '
                                     '_miss.append(f"上游最後一次錯誤：{scrub_secrets(view.upstream_error)}")   '
                                     '# 具體錯誤原樣（洗過）\n'
                                     '        elif upstream_state_text(_up):\n'
                                     '            _miss.append(upstream_state_text(_up))\n'
                                     '    return Basis(\n',
                                     '        _miss.insert(0, f"指數線：{scrub_secrets(view.error)}")\n'
                                     '    if view is not None and view.ok and '
                                     'view.upstream_error:\n'
                                     '        '
                                     '_miss.append(f"上游最後一次錯誤：{scrub_secrets(view.upstream_error)}")\n'
                                     '    return Basis(\n'))}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def b2_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`(或 repo 相對路徑)與原始碼,換回 B2 之前的寫法(無 pair 則原樣;只套一次)。"""
    # 📌 Issue #1099 PR-1(TWII 日 K OHLC 唯讀契約,2026-11-09;有意識的接鏈,⛔ 不是漏改):PR-1 在 B2 之後
    #   於 `macro_cache_reader.py` 新增 `load_twii_ohlc` ⇒ 鏈頭往前接一節,先把 PR-1 換回(只套一次;⛔ 不動本表與 B2_BASE_SHA)。
    from tests.test_twii_ohlc_revert_chain import twii_ohlc_revert_for
    code = twii_ohlc_revert_for(file_path, code)
    rel = _rel(file_path)
    pairs = B2_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} B2 還原組錨點漂移(各組出現次數 {counts};應全 1 或全 0)—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_b2_revert_is_exact_base_source():
    assert set(B2_REVERT_PAIRS) == set(B2_BASE_SHA)
    for rel in sorted(B2_REVERT_PAIRS):
        code = b2_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == B2_BASE_SHA[rel], rel


def test_b2_revert_is_idempotent():
    for rel in sorted(B2_REVERT_PAIRS):
        once = b2_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert b2_revert_for(rel, once) == once, rel


def test_b2_anchors_present_once_in_current_file_and_never_in_base():
    """每個新片段在現行檔恰 1 次;還原後 0 次 —— 防止還原組變成空轉。"""
    for rel, pairs in B2_REVERT_PAIRS.items():
        cur = (REPO / rel).read_text(encoding="utf-8")
        base = b2_revert_for(rel, cur)
        for new, _old in pairs:
            assert cur.count(new) == 1 and base.count(new) == 0, (rel, new[:60])


def test_b2_revert_removes_every_upstream_state_marker():
    """自證:還原後的基底碼不含任何 B2 識別字(分流邏輯真的在被還原的區塊內,不是漏掉一塊)。"""
    for rel in B2_REVERT_PAIRS:
        base = b2_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        for tok in ("upstream_state", "classify_upstream", "fetch_evidence", "shared.upstream_state"):
            assert tok not in base, (rel, tok)
        cur = (REPO / rel).read_text(encoding="utf-8")
        assert "upstream_state" in cur


def test_chain_head_calls_b2_first():
    """原鏈頭 `p4_revert_for` 必須先呼叫本節,再 D3、再 D1、再 D2、再 P4(否則舊批次的基底 sha 守衛看到的是 B2 的新寫法)。"""
    import inspect

    from tests.test_p4_revert_chain import p4_revert_for
    src = inspect.getsource(p4_revert_for)
    assert (src.index("b2_revert_for(file_path, code)")
            < src.index("d3_revert_for(file_path, code)")
            < src.index("d1_revert_for(file_path, code)")
            < src.index("d2stale_revert_for(file_path, code)")
            < src.index("P4_REVERT_PAIRS.get(rel"))
