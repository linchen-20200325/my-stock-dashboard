"""tests/test_p4_revert_chain.py — Phase 4 P4-1（📊 市場頁第一屏，2026-10-30，客戶 DEC-117）的還原鏈新頭節。

為什麼需要：本批改了被舊鏈以基底 sha 守衛的 `src/ui/views/page_market.py`（`tests/test_nav1_revert_chain.py`、
`tests/test_uim_revert_chain.py` 經 `uim_revert_for` 管）⇒ 在鏈頭**往前接一節**，先把本批改動換回
（比照 `uim_revert_for` 接在 `xvext_revert_for` 開頭的作法；⛔ 不動任何舊表與舊基底 sha）。
`uim_revert_for` 第一步呼叫本節（再往下是 UI-M 自己的表 → xvext → dec102 → asof → …）。

基底 ＝ `7484c57b`（main，Phase 4 開工前）。pair 由 `difflib` 依行分組、最小唯一上下文產生，產生時驗證：
「套用後逐字等於基底、每個新寫法在現行檔恰出現 1 次、套用後 0 次」。基底 sha 寫死以免測試依賴 git。
⚠️ P4-2 若再動 `page_market.py`：以**同一基底**（`7484c57b`）對當時最終檔重產本表（⛔ 另立新基底、⛔ 改舊表）。
✅ P4-2（2026-10-31，圖區）已動 `page_market.py` ⇒ 本表已以**同一基底**對 P4-2 最終檔重產（4 組；基底 sha 不變）。

⚠️ 只套一次（idempotent）：同一份程式碼可能經過兩個掛點（nav1 與 uim 兩條路都會走到本節）。判定（整檔一起看）：
每一組的 `新寫法` 都恰好出現一次 ⇒ 換回；都 0 次 ⇒ 已被前一個掛點換回；其餘 ⇒ AssertionError（錨點漂移，須重產）。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

P4_BASE_SHA = {'src/ui/views/page_market.py': '59c9801be3c631de6f85afd4f803a56d3bc5c4cedcbe78c3f01818200cdef491'}

P4_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'src/ui/views/page_market.py': (('  · 頁內標題字樣「📊 市場」（本地常數 `_market_blocks.PAGE_TITLE`；⛔ 不改 '
                                  '`shared/ia_nav.PAGE_LABELS`）。\n'
                                  '\n'
                                  '═══ Phase 4 P4-1（2026-10-30）落地 DEC-117 已核准線框第一屏（有意識的修改，⛔ 不是漏刪）═══════════════\n'
                                  '第一屏改為「頁首（＋更新 CTA）→ 今日結論 → 3 個核心狀態 → ⚡ 需要處理 → AI／資料狀態 → 圖區」（Q5=B 新順序，\n'
                                  '取代 DEC-105 1A 在本頁的舊相對順序）；圖區緊接 L1 決策區（Q7），本批圖區本身不動（P4-2）。\n'
                                  '  · Q1=B：~~Hero 4 卡~~ → 3 個核心狀態 tile（`blocks.render_core_tiles`）；「🚀 更新今日戰情」改為頁首主 '
                                  'CTA\n'
                                  '    （`blocks.render_update_cta`；與今天頁同一組 form／session key，radio＋長說明收進「更新選項」，Q8b）。\n'
                                  '  · 狀態列 `status_line()` 原樣呼叫、**逐字拆兩處**：更新時間那半在頁首、指標危險度覆蓋率那半在風險 tile（C6-4）。\n'
                                  '    「逐項資料日：尚未提供…」整句與資料健康指路下沉到「資料來源與完整度」展開區（線框 P-03，只下沉）。\n'
                                  '  · 更新報告（`_render_report_guarded`）仍緊接更新鈕下方（X3／X10 字樣不必改）；其主體本來就是預設收合的\n'
                                  '    expander，真錯誤（取不到／回空）依 2026-09-24 客戶裁示照舊留在收合區外。\n'
                                  '    📌 2026-10-30 更正（有意識的更新，不是漏刪；決策者 客戶 DEC-118 問題 2=D1＋AI 總管判定 Z；上兩行原文保留＝P4-1 第一版\n'
                                  '    的行為）：**現行**——報告**沒有**真錯誤時仍在更新鈕下方（預設收合）；報告含真錯誤（取不到／回空），或不是現行報告型別\n'
                                  '    （舊格式）、或在原位渲染時拋例外 ⇒ 整份既有報告改畫在**今日結論正下方**（真錯誤外露、不收合）。CTA 與今日結論之間\n'
                                  '    在任何狀態都沒有外露內容。\n'
                                  '  · 今日結論句與標題逐字不改（DEC-081 Q2-1），只改位置。\n'
                                  '\n'
                                  '═══ Phase 4 P4-2（2026-10-30）落地 DEC-117 已核准線框圖區（有意識的修改，⛔ 不是漏刪）═══════════════\n'
                                  '~~圖 A～D 兩欄網格（A｜B、C｜D）~~ → Primary（圖 A，整列寬）緊接 L1 決策區；其後 Secondary 國際小倍數 → 圖 D → 圖 '
                                  'C（整列寬；\n'
                                  '線框 §4.1 順序）。各圖的「▸ 為什麼／來源／限制／去哪補」摺疊在 `_market_blocks`；「去哪補」指向的 L2 展開區標題與下方展開區\n'
                                  '共用同一個字串（本檔算一次）。L2／L3 展開區內容一字未改。\n'
                                  '\n',
                                  '  · 頁內標題字樣「📊 市場」（本地常數 `_market_blocks.PAGE_TITLE`；⛔ 不改 '
                                  '`shared/ia_nav.PAGE_LABELS`）。\n'
                                  '\n'),
                                 ('\n'
                                  '    # ── 層 1：首屏（P4-1，DEC-117 Q5=B 新順序）────────────────────────────\n'
                                  '    # 狀態列逐字拆兩半（`status_line` 的分隔字＝「｜」）：更新時間（≠ 資料日）在頁首、覆蓋率在風險 tile（C6-4）。\n'
                                  '    # QA 修正輪：分隔字必須恰好一個，否則 fail loud（§1；⛔ 拆錯位置把半句話放到錯的地方）。\n'
                                  '    _status = status_line(_report, _danger)\n'
                                  '    if _status.count("｜") != 1:\n'
                                  '        raise ValueError(f"狀態列應恰含一個「｜」才能拆成更新時間／覆蓋率兩半，實得：{_status!r}")\n'
                                  '    _time_text, _coverage_text = _status.split("｜")\n'
                                  '    # DEC-118 問題 2=D1（客戶 2026-10-30）＋總管判定 Z：報告含**真錯誤**（取不到／回空）時，整份既有報告（真錯誤 '
                                  '`st.error`\n'
                                  '    #   ＋預設收合的報告標題）改畫在今日結論正下方 —— 真錯誤外露、不擠出結論；CTA 與結論之間只剩收合標題列。\n'
                                  '    #   ⛔ 拆 `page_today._render_refresh_report`（禁改，DEC-081 Q1=C）、⛔ 複寫。\n'
                                  '    #   QA 第二輪：不是現行報告型別（舊格式）或判斷時拋例外 ⇒ **一律視為有真錯誤**、移到結論下方，由\n'
                                  '    #   `_render_report_guarded` 在那裡講出來並清掉（§1：紅字不得落在 CTA 與結論之間）。\n'
                                  '    from src.services.macro_refresh_service import MacroRefreshReport\n'
                                  '    try:\n'
                                  '        _report_errors_below = _report is not None and (\n'
                                  '            not isinstance(_report, MacroRefreshReport) or bool(_report.failures or '
                                  '_report.empties))\n'
                                  '    except Exception as _e:  # noqa: BLE001 — 只決定位置；真正的紅字由 `_render_report_guarded` '
                                  '在結論下方講出來\n'
                                  '        print(f"[views/page_market] 判斷更新報告有無真錯誤時讀不出來：{_e!r} —— 視為有真錯誤，移到結論下方")\n'
                                  '        _report_errors_below = True\n'
                                  '    # L1 決策區包在一個具名容器裡：窄螢幕只在這裡壓縮間距（`blocks.P4M_LAYOUT_CSS`；只排版、不藏內容）。\n'
                                  '    blocks.render_layout_css()\n'
                                  '    with st.container(key=blocks.P4M_L1_KEY):\n'
                                  '        # ① 頁首（＋主 CTA）：桌機與標題同列右側；窄螢幕 Streamlit 自動疊成「標題 → CTA」。\n'
                                  '        _head = st.columns([3, 2])\n'
                                  '        with _head[0]:\n'
                                  '            st.markdown(f"## {blocks.PAGE_TITLE}")\n'
                                  '            st.caption(blocks.PAGE_SUBTITLE)\n'
                                  '            '
                                  'st.caption(f"{_time_text}｜{blocks.data_date_text(_session.get(\'mkt_info\'))}")\n'
                                  '        with _head[1]:\n'
                                  '            # 更新鈕與今天頁同一組 form／session key（⛔ 不另寫第二套更新流程）；form key 兩頁共用沒有衝突：側欄一次只選得到\n'
                                  '            # 一頁（`app.py` 的 `_IA_PAGE` 分支＋`st.stop()`），兩頁不會出現在同一輪 script run。\n'
                                  '            # 已套用模式與上一次的更新報告刻意共用 —— 按一次更新，兩頁看到的是同一份結果。\n'
                                  '            blocks.render_update_cta(_session)\n'
                                  '        if _report is not None and not _report_errors_below:\n'
                                  '            # 乾淨報告畫在佔位內：渲染途中拋例外 ⇒ 清掉已畫一半的內容、改到結論下方由 `_render_report_guarded` 講出來\n'
                                  '            # （⛔ 半份報告或紅字留在 CTA 與結論之間）。\n'
                                  '            _report_slot = st.empty()\n'
                                  '            try:\n'
                                  '                with _report_slot.container():\n'
                                  '                    today._render_refresh_report(_report)\n'
                                  '            except Exception as _e:  # noqa: BLE001 — 不吞：下方 '
                                  '`_render_report_guarded` 會再畫一次並講出來\n'
                                  '                print(f"[views/page_market] 更新報告在原位畫不出來：{_e!r} —— 改到今日結論下方處理")\n'
                                  '                _report_slot.empty()\n'
                                  '                _report_errors_below = True\n'
                                  '\n'
                                  '        # ② 今日結論（逐字；只改位置）。\n'
                                  '        section_header(CONCLUSION_HEADING)\n'
                                  '        try:\n'
                                  '            '
                                  'st.markdown(build_market_conclusion(regime_text=regime_clause(_regime_tile, '
                                  '_regime),\n'
                                  '                                                '
                                  'danger_text=danger_clause(_danger_tile)))\n'
                                  '        except ValueError as _e:  # §1：字樣不合規 ⇒ 講出來，⛔ 不自己改寫\n'
                                  '            st.error(f"結論句組不出來：{_e}", icon="❌")\n'
                                  '        if _report_errors_below:\n'
                                  '            _render_report_guarded(_report)   # D1：真錯誤緊接今日結論（外露，不收合）\n'
                                  '\n'
                                  '        # ③ 3 個核心狀態 tile（位階 tile 的外露字＝結論句同一支 `regime_clause`）。\n'
                                  '        blocks.render_core_tiles(\n'
                                  '            regime_tile=_regime_tile, regime_face=regime_clause(_regime_tile, '
                                  '_regime),\n'
                                  '            regime_badge=(card_badge_text(_regime_tile) if _regime_tile.card.state '
                                  '== UI_LIVE else ""),\n'
                                  '            exposure_tile=_exposure, alloc=_alloc, alloc_error=_alloc_err, '
                                  'risks=_risks,\n'
                                  '            coverage_text=_coverage_text,\n'
                                  '            # QA 修正輪（客戶 Q6 真錯誤外露逐字）：讀契約失敗時，tile 外露 X1 同一句紅字（字樣與 `_render_x1` 相同）。\n'
                                  '            regime_error_line=(f"市場位階契約讀不出來：`{scrub_secrets(_regime_err)}`" if '
                                  '_regime_err else ""))\n'
                                  '\n'
                                  '        # ④ ⚡ 需要處理（一行 bar＋展開清單；只轉述既有警示＋建議持股的衝突提示；三態判別沿用 `build_key_alert_tile`）。\n'
                                  '        blocks.render_alerts_block(alerts_tile=_alerts_tile, alerts=_alerts, '
                                  'scanned=_scanned,\n'
                                  '                                   alerts_error=_alerts_err, alloc=_alloc)\n'
                                  '        # ⑤ AI／資料狀態一行。之後緊接圖區（Q7：中間⛔ 插任何 L2／L3 長內容）。\n'
                                  '        blocks.render_ai_status_line()\n'
                                  '\n'
                                  '    # 圖區（P4-2，DEC-117 Q4=P-B）：Primary（圖 A）緊接 L1 決策區、整列寬；其後 Secondary 依線框 §4.1 順序\n'
                                  '    #   國際小倍數 → 圖 D → 圖 C（各自整列寬）。各圖摺疊「去哪補」指向的 L2 展開區標題在這裡算一次、與下方展開區共用同一個字串。\n'
                                  '    _tw_raw_label = f"台股盤勢（{RAW_DATA_SUFFIX}）"\n'
                                  '    _intl_raw_label = f"國際市場（{RAW_DATA_SUFFIX}）"\n'
                                  '    blocks.render_chart_a(_session, where_label=_tw_raw_label)\n'
                                  '    blocks.render_chart_b(_session, source_note=FRAME_SOURCE_NOTE["intl"], '
                                  'where_label=_intl_raw_label)\n'
                                  '    blocks.render_chart_d(_risks)\n'
                                  '    blocks.render_chart_c(where_label=X9_TITLE)\n'
                                  '\n',
                                  '\n'
                                  '    # ── 層 1：首屏 ───────────────────────────────────────────────\n'
                                  '    st.markdown(f"## {blocks.PAGE_TITLE}")\n'
                                  '    st.caption(blocks.PAGE_SUBTITLE)\n'
                                  '    st.markdown(status_line(_report, _danger))\n'
                                  '    st.caption(AS_OF_NOT_PROVIDED if _in_default_nav() else\n'
                                  '               f"{AS_OF_NOT_PROVIDED}｜🩺 資料健康：請到 "\n'
                                  '               f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")\n'
                                  '    # Hero 4 卡。更新鈕與今天頁同一支 form（⛔ 不另寫第二套更新流程）；form key 兩頁共用沒有衝突：側欄一次只選得到\n'
                                  '    # 一頁（`app.py` 的 `_IA_PAGE` 分支＋`st.stop()`），兩頁不會出現在同一輪 script run。\n'
                                  '    # 已套用模式與上一次的更新報告刻意共用 —— 按一次更新，兩頁看到的是同一份結果。\n'
                                  '    blocks.render_hero(_session, regime_tile=_regime_tile, '
                                  'exposure_tile=_exposure,\n'
                                  '                       alloc=_alloc, alloc_error=_alloc_err, risks=_risks)\n'
                                  '    if _report is not None:\n'
                                  '        _render_report_guarded(_report)\n'
                                  '\n'
                                  '    section_header(CONCLUSION_HEADING)\n'
                                  '    try:\n'
                                  '        st.markdown(build_market_conclusion(regime_text=regime_clause(_regime_tile, '
                                  '_regime),\n'
                                  '                                            '
                                  'danger_text=danger_clause(_danger_tile)))\n'
                                  '    except ValueError as _e:  # §1：字樣不合規 ⇒ 講出來，⛔ 不自己改寫\n'
                                  '        st.error(f"結論句組不出來：{_e}", icon="❌")\n'
                                  '\n'
                                  '    # ⚡ 需要處理（只轉述既有警示＋建議持股的衝突提示；三態判別沿用 `build_key_alert_tile`）。\n'
                                  '    blocks.render_alerts_block(alerts_tile=_alerts_tile, alerts=_alerts, '
                                  'scanned=_scanned,\n'
                                  '                               alerts_error=_alerts_err, alloc=_alloc)\n'
                                  '\n'
                                  '    # 圖 A～D（兩欄網格；窄螢幕由 Streamlit 自動改一欄，順序同下）。\n'
                                  '    _r1 = st.columns(2)\n'
                                  '    with _r1[0]:\n'
                                  '        blocks.render_chart_a(_session)\n'
                                  '    with _r1[1]:\n'
                                  '        blocks.render_chart_b(_session, source_note=FRAME_SOURCE_NOTE["intl"])\n'
                                  '    _r2 = st.columns(2)\n'
                                  '    with _r2[0]:\n'
                                  '        blocks.render_chart_c()\n'
                                  '    with _r2[1]:\n'
                                  '        blocks.render_chart_d(_risks)\n'
                                  '\n'),
                                 ('            today._render_tiles(_tiles_by_bucket.get(_b, ()))\n'
                                  '    with st.expander(_tw_raw_label, expanded=False):\n'
                                  '        _render_x5(_session)\n'
                                  '    with st.expander(_intl_raw_label, expanded=False):\n'
                                  '        _render_x6(_session)\n',
                                  '            today._render_tiles(_tiles_by_bucket.get(_b, ()))\n'
                                  '    with st.expander(f"台股盤勢（{RAW_DATA_SUFFIX}）", expanded=False):\n'
                                  '        _render_x5(_session)\n'
                                  '    with st.expander(f"國際市場（{RAW_DATA_SUFFIX}）", expanded=False):\n'
                                  '        _render_x6(_session)\n'),
                                 ('    with st.expander("資料來源與完整度", expanded=False):\n'
                                  '        # P4-1（線框 P-03，只下沉）：原首屏「逐項資料日」整句與資料健康指路移到這裡，字樣逐字。\n'
                                  '        st.caption(AS_OF_NOT_PROVIDED if _in_default_nav() else\n'
                                  '                   f"{AS_OF_NOT_PROVIDED}｜🩺 資料健康：請到 "\n'
                                  '                   f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")\n'
                                  '        st.markdown(\n',
                                  '    with st.expander("資料來源與完整度", expanded=False):\n        st.markdown(\n'))}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def p4_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 Phase 4 P4-1 之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    pairs = P4_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} Phase 4 P4-1 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須以同一基底重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_p4_revert_is_exact_base_source():
    assert set(P4_REVERT_PAIRS) == set(P4_BASE_SHA)
    for rel in sorted(P4_REVERT_PAIRS):
        code = p4_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == P4_BASE_SHA[rel], rel


def test_p4_revert_is_idempotent():
    for rel in sorted(P4_REVERT_PAIRS):
        once = p4_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert p4_revert_for(rel, once) == once, rel


def test_each_new_snippet_appears_exactly_once_now_and_never_in_base():
    """產生時的三條件在測試期再驗一次（錨點漂移當場紅，⛔ 靜默套錯位置）。"""
    for rel, pairs in P4_REVERT_PAIRS.items():
        cur = (REPO / rel).read_text(encoding="utf-8")
        base = p4_revert_for(rel, cur)
        for new, _old in pairs:
            assert cur.count(new) == 1 and base.count(new) == 0, (rel, new[:60])


def test_chain_head_calls_p4_first():
    """`uim_revert_for` 必須先呼叫本節（再處理 UI-M 自己的表）；`xvext_revert_for` 仍先呼叫 `uim_revert_for`。"""
    import inspect

    from tests.test_uim_revert_chain import uim_revert_for
    from tests.test_xvext_revert_chain import xvext_revert_for
    src = inspect.getsource(uim_revert_for)
    assert src.index("p4_revert_for(file_path, code)") < src.index("UIM_REVERT_PAIRS.get(rel")
    xv = inspect.getsource(xvext_revert_for)
    assert xv.index("uim_revert_for(file_path, code)") < xv.index("dec102_revert_for(file_path, code)")
