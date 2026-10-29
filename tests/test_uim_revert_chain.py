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

UIM_BASE_SHA = {'src/compute/macro/macro_helpers.py': '2f497bfdf4891d69f8116311ca72ddf773da1c4a976b71cc34a510c0057ce8b9',
 'src/ui/views/page_market.py': '9ea605156d0b98f89548bc1f9c94a5e0ea918ee5afe03c2b28a11d24da3fdd1b'}

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
                                         '            "details": details,\n        }\n')),
 'src/ui/views/page_market.py': (('\n'
                                  '═══ UI-M（2026-10-29）落地 D2.5 已核准線框＋A 規格（DEC-092）═══════════════════\n'
                                  '首屏改為「Hero 4 卡（市場狀態｜建議總持股水位｜今日主要風險｜更新）→ 今日結論句 → ⚡ 需要處理 → 圖 A～D」，\n'
                                  '新區塊與「🔍 查看依據」六欄元件在 `_market_blocks.py`（本檔只編排）。⚠️ 有意識的修改，⛔ 不是漏刪：\n'
                                  '  · 原「趨勢兩卡」「風險上限卡位」「卡①②③ 三欄並排」被取代 —— 台股／國際趨勢結論改在圖 A／圖 B 底下仍固定\n'
                                  '    「⬜ 尚未定義」；「風險上限」客戶字樣併入水位卡的說明；卡①（出手區間，含 risk_cap.v2）整段移入水位卡的\n'
                                  '    「🔍 查看依據」；卡②（指標危險度）移到「指標明細（16 項）」展開區最上面。**能力保留、沒有刪**。\n'
                                  '  · 今日結論句、X1～X11 展開區、更新模式 radio 與更新報告**原樣保留**（parity 腳本逐字比對）。\n'
                                  '  · 頁內標題字樣「📊 市場」（本地常數 `_market_blocks.PAGE_TITLE`；⛔ 不改 '
                                  '`shared/ia_nav.PAGE_LABELS`）。\n'
                                  '\n'
                                  '掛載：`app.py::_ia_view_market()` 於側欄「🆕 新版戰情室（試用中）」radio 選到本頁時\n',
                                  '\n掛載：`app.py::_ia_view_market()` 於側欄「🆕 新版戰情室（試用中）」radio 選到本頁時\n'),
                                 ('from shared.inst_net import is_net_observed\n'
                                  'from shared.market_conclusion import build_market_conclusion\n'
                                  'from shared.secret_scrub import scrub_secrets\n'
                                  'from shared.ui_state import UI_DEGRADED, UI_LIVE, UI_PARTIAL\n'
                                  'from src.ui.views import _market_blocks as blocks\n'
                                  'from src.ui.views import page_today as today\n'
                                  'from src.ui.views._market_blocks import TREND_PENDING_WHY  # noqa: F401 — '
                                  '趨勢「等客戶定義」說明（原定義在本檔，UI-M 移入 blocks；re-export 保 `M.TREND_PENDING_WHY`）\n'
                                  'from src.ui_v2 import components as v2_components\n',
                                  'from shared.inst_net import is_net_observed\n'
                                  'from shared.market_conclusion import (\n'
                                  '    CONCEPT_INTL_TREND,\n'
                                  '    CONCEPT_RISK_CAP,\n'
                                  '    CONCEPT_TW_TREND,\n'
                                  '    RISK_CAP_PENDING_TEXT,\n'
                                  '    TREND_UNDEFINED_TEXT,\n'
                                  '    build_market_conclusion,\n'
                                  ')\n'
                                  'from shared.secret_scrub import scrub_secrets\n'
                                  'from shared.ui_state import UI_DEGRADED, UI_LIVE, UI_PARTIAL\n'
                                  'from src.ui.views import page_today as today\n'
                                  'from src.ui_v2 import components as v2_components\n'),
                                 ('# ══════════════════════════════════════════════════════════════════\n'
                                  '#: ~~頁首問句~~ 已被 UI-M 取代為 `_market_blocks.PAGE_SUBTITLE`（A 規格 §2.1 '
                                  '客戶原文）。常數保留作歷史字樣，本頁不再引用。\n'
                                  'PAGE_QUESTION: str = "現在市場環境適不適合投資？目前可以承擔多少風險？"\n'
                                  'CONCLUSION_HEADING: str = "今日結論（五項各自判斷，只並列，不合成）"\n'
                                  '#: 第 3 層原始資料區的標題後綴（Q3=A 原文）。\n',
                                  '# ══════════════════════════════════════════════════════════════════\n'
                                  'PAGE_QUESTION: str = "現在市場環境適不適合投資？目前可以承擔多少風險？"\n'
                                  'CONCLUSION_HEADING: str = "今日結論（五項各自判斷，只並列，不合成）"\n'
                                  '#: 趨勢兩卡的說明（Q3=A：只說定義在等客戶，⛔ 不帶任何指標、燈色、多空字樣）。\n'
                                  'TREND_PENDING_WHY: str = "怎麼判斷還在等您定義；定義之前本頁不給這一項結論。"\n'
                                  '#: 第 3 層原始資料區的標題後綴（Q3=A 原文）。\n'),
                                 ('# ══════════════════════════════════════════════════════════════════\n'
                                  'def _render_raw_table(rows: Sequence[tuple[str, str, str]], *, '
                                  'empty_text: str) -> None:\n',
                                  '# ══════════════════════════════════════════════════════════════════\n'
                                  'def _render_plain_card(title: str, body: str, why: str = "") -> None:\n'
                                  '    """不帶燈色、不帶狀態徽章的卡（趨勢兩卡、風險上限卡位用 —— Q2-2／Q3=A：只有文字）。"""\n'
                                  '    with st.container(border=True):\n'
                                  '        st.markdown(f"**{title}**")\n'
                                  '        st.markdown(body)\n'
                                  '        if why:\n'
                                  '            st.caption(why)\n'
                                  '\n'
                                  '\n'
                                  'def _render_raw_table(rows: Sequence[tuple[str, str, str]], *, '
                                  'empty_text: str) -> None:\n'),
                                 ('def render_page_market() -> None:\n'
                                  '    """📊 市場（IA v2，UI-M 版）。卡①～③、16 盞燈、今日關鍵、更新鈕都呼叫 `page_today` 的同一段程式。"""\n'
                                  '    _session = st.session_state\n',
                                  'def render_page_market() -> None:\n'
                                  '    """📊 大盤（IA v2）。卡①～③、16 盞燈、今日關鍵、更新鈕都呼叫 `page_today` 的同一段程式。"""\n'
                                  '    _session = st.session_state\n'),
                                 ('        _attempt = None\n'
                                  '    # 燈卡「變化方向」：只算一次，hero／圖 D／指標明細三處共用（修前只有指標明細展開區在算，同一支 loader）。\n'
                                  '    _directions = today._load_lamp_directions(_session)\n'
                                  '    # 今日主要風險（hero）與圖 D 的**單一來源**：同一個 `MarketRisks`。\n'
                                  '    _risks = blocks.build_market_risks(_readout, _directions)\n'
                                  '\n',
                                  '        _attempt = None\n\n'),
                                 ('        macro_attempt=_attempt, breadth_proxy=_breadth_proxy)\n'
                                  '    _alerts_tile = today.build_key_alert_tile(\n'
                                  '        _alerts, requested=_readout.requested, '
                                  'threshold_scanned=_scanned,\n'
                                  '        error=_alerts_err, band_zh_color=_band_zh)\n'
                                  '\n'
                                  '    # ── 層 1：首屏 ───────────────────────────────────────────────\n'
                                  '    st.markdown(f"## {blocks.PAGE_TITLE}")\n'
                                  '    st.caption(blocks.PAGE_SUBTITLE)\n'
                                  '    st.markdown(status_line(_report, _danger))\n',
                                  '        macro_attempt=_attempt, breadth_proxy=_breadth_proxy)\n'
                                  '\n'
                                  '    # ── 層 1：首屏 ───────────────────────────────────────────────\n'
                                  '    st.markdown(f"## {ia_nav.page_label(ia_nav.PAGE_MARKET)}")\n'
                                  '    st.caption(PAGE_QUESTION)\n'
                                  '    st.markdown(status_line(_report, _danger))\n'),
                                 ('               '
                                  'f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")\n'
                                  '    # Hero 4 卡。更新鈕與今天頁同一支 form（⛔ 不另寫第二套更新流程）；form key 兩頁共用沒有衝突：側欄一次只選得到\n'
                                  '    # 一頁（`app.py` 的 `_IA_PAGE` 分支＋`st.stop()`），兩頁不會出現在同一輪 script run。\n'
                                  '    # 已套用模式與上一次的更新報告刻意共用 —— 按一次更新，兩頁看到的是同一份結果。\n'
                                  '    blocks.render_hero(_session, regime_tile=_regime_tile, '
                                  'exposure_tile=_exposure,\n'
                                  '                       alloc=_alloc, alloc_error=_alloc_err, '
                                  'risks=_risks)\n'
                                  '    if _report is not None:\n',
                                  '               '
                                  'f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")\n'
                                  '    # 與今天頁同一支 form（⛔ 不另寫第二套更新流程）。form key 兩頁共用沒有衝突：側欄一次只選得到\n'
                                  '    # 一頁（`app.py` 的 `_IA_PAGE` 分支＋`st.stop()`），兩頁不會出現在同一輪 script run。\n'
                                  '    # 已套用模式與上一次的更新報告刻意共用 —— 按一次更新，兩頁看到的是同一份結果。\n'
                                  '    today._render_update_form(_session)\n'
                                  '    if _report is not None:\n'),
                                 ('\n'
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
                                  '        blocks.render_chart_b(_session, '
                                  'source_note=FRAME_SOURCE_NOTE["intl"])\n'
                                  '    _r2 = st.columns(2)\n'
                                  '    with _r2[0]:\n'
                                  '        blocks.render_chart_c()\n'
                                  '    with _r2[1]:\n'
                                  '        blocks.render_chart_d(_risks)\n'
                                  '\n',
                                  '\n'
                                  '    # 今日關鍵警示（一行；與今天頁 ④ 同一支）。\n'
                                  '    today._render_tiles((today.build_key_alert_tile(\n'
                                  '        _alerts, requested=_readout.requested, '
                                  'threshold_scanned=_scanned,\n'
                                  '        error=_alerts_err, band_zh_color=_band_zh),), cols=1)\n'
                                  '\n'
                                  '    # 3 欄網格（窄螢幕由 Streamlit 自動改一欄，順序同下）。\n'
                                  '    _r1 = st.columns(3)\n'
                                  '    with _r1[0]:\n'
                                  '        today._render_one(_regime_tile)\n'
                                  '    with _r1[1]:\n'
                                  '        _render_plain_card(CONCEPT_TW_TREND, TREND_UNDEFINED_TEXT, '
                                  'TREND_PENDING_WHY)\n'
                                  '    with _r1[2]:\n'
                                  '        _render_plain_card(CONCEPT_INTL_TREND, TREND_UNDEFINED_TEXT, '
                                  'TREND_PENDING_WHY)\n'
                                  '    _r2 = st.columns(3)\n'
                                  '    with _r2[0]:\n'
                                  '        today._render_one(_danger_tile)\n'
                                  '    with _r2[1]:\n'
                                  '        _render_plain_card(CONCEPT_RISK_CAP, RISK_CAP_PENDING_TEXT)\n'
                                  '    with _r2[2]:\n'
                                  '        today._render_one(_exposure)\n'
                                  '\n'),
                                 ('    with st.expander("指標明細（16 項）", expanded=False):\n'
                                  '        # UI-M：原首屏卡②「指標危險度」退到這裡（內容保留，同一段程式、同一張卡）。\n'
                                  '        today._render_one(_danger_tile)\n'
                                  '        _tiles_by_bucket = today.build_indicator_tiles(\n'
                                  '            _readout, band_label=_band_label, thr_text=_thr_text, '
                                  'l4_error=_l4_err,\n'
                                  '            directions=_directions)\n'
                                  '        st.markdown(today.coverage(_tiles_by_bucket).text())\n',
                                  '    with st.expander("指標明細（16 項）", expanded=False):\n'
                                  '        _tiles_by_bucket = today.build_indicator_tiles(\n'
                                  '            _readout, band_label=_band_label, thr_text=_thr_text, '
                                  'l4_error=_l4_err,\n'
                                  '            directions=today._load_lamp_directions(_session))\n'
                                  '        st.markdown(today.coverage(_tiles_by_bucket).text())\n'))}


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
