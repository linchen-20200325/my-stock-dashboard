"""tests/test_nav1_revert_chain.py — NAV-1 回修（QA MAJOR-1）對 `page_hold.py`／`page_me.py`／`page_market.py` 的還原鏈新頭節。

為什麼需要：NAV-1 回修在這三個新 UI 檔加了「預設（新四頁）模式的頁內文字」分流（只動呈現層；legacy 原句一字不變）。
舊鏈（`sheet_safety_revert_for` → `d2_revert_for` → `me_p1_revert_for` → … → 各批次基底 sha 守衛）用「新寫法 → 舊寫法」錨點把這幾個檔
還原成各自的基底 sha；本批的改動落在它們的守衛範圍內 ⇒ 在鏈頭**往前接一節**，先把 NAV-1 回修換回
（比照 `d2_revert_for` 接 `sheet_safety_revert_for` 的作法；⛔ 不動任何舊表與舊基底 sha）。

基底 ＝ NAV-1 回修開工前的 commit（`08a3e43` 之後、本批 commit 之前的工作樹）。pair 由 `difflib` 分組產生，並於產生時驗證
「套用後逐字等於基底、且每個新寫法在現行檔恰出現 1 次」。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

NAV1_BASE_SHA = {'src/ui/views/page_hold.py': '2feece1433640e800aaba68b17b21faa2819e52a5fd55ec9d3c6197d248a30b3',
 'src/ui/views/page_market.py': '2ca54b2f1e3c16d3cc7ae25d36e2e33f8b7fa5d35b52b70ca0e55ea3ccd40e7d',
 'src/ui/views/page_me.py': 'ce08537b106d58bd28dd7fbdbe2064c1f3f4dda6f1e39bf90f7b0bc456b2348f'}

NAV1_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {'src/ui/views/page_hold.py': (('_V2_OLD_UI: str = "目前請切回舊版 → 📁 組合管理"   # 客戶原句的開頭一段（K1：原文摘錄）\n'
                                '\n'
                                '# '
                                '══════════════════════════════════════════════════════════════════\n'
                                '# NAV-1 回修（QA MAJOR-1）：預設（新四頁）模式的「切回舊版」類指路句 —— 只在**呈現層**替換\n'
                                '# '
                                '══════════════════════════════════════════════════════════════════\n'
                                '# 預設模式下（`app.py` 在 session 明確寫 `_nav4_legacy = '
                                'False`），舊版入口（側欄「不使用」radio、舊 📁 組合管理頁籤）\n'
                                '# 對一般使用者**不存在**（DEC-097）⇒ 客戶原句「目前請切回舊版 → 📁 組合管理；新版 CRUD '
                                '會在下一階段處理。」成了死路。\n'
                                '# 做法（⚠️ 有意識的修改，⛔ 不是漏刪）：`ia_nav.CONTENT_EDIT_OLD_UI_WHERE`（客戶逐字句，⛔ '
                                '不改常數）與本檔 `_V2_OLD_UI`\n'
                                '# 在**最後送進畫面的那一刻**（`_render_one_v2`／唯讀 caption）依 session 旗標替換：\n'
                                '#   · legacy 模式（旗標為 True）或旗標不存在（單元測試／直接呼叫）：原句逐字不變；\n'
                                '#   · 預設模式（旗標明確為 False）：換成不指向 legacy 的誠實句（不新增任何 UI 元件、不放 legacy '
                                '連結）。\n'
                                '# ⚠️ 本批**不改** `where_to_find` 產生的路徑名（🛡️持股›…、📊 大盤›🚦 今天、🩺／📖 —— 牽動 '
                                'ia_nav 46 字上限與 revert chain，\n'
                                '#    併 I-1 另批）；這些路徑名在預設模式仍會出現（已知限制，見 NAV-1 spec §7）。\n'
                                '# ⚠️ 旗標 key 的字面值與 `shared/ia_nav4.LEGACY_SESSION_KEY` 各一份（本檔不得 '
                                'import ia_nav4：legacy 路徑零依賴新模組；\n'
                                '#    相等由 `tests/test_nav1_default_mode_text.py` 釘住）。\n'
                                '_NAV4_LEGACY_SESSION_KEY: str = "_nav4_legacy"\n'
                                'DEFAULT_MODE_NOT_YET: str = "此功能新版尚未提供，後續批次處理。"\n'
                                'DEFAULT_MODE_NOT_YET_SHORT: str = "此功能新版尚未提供"\n'
                                '\n'
                                '\n'
                                'def _in_default_nav() -> bool:\n'
                                '    """預設（新四頁）模式？只有 session 旗標**明確為 False** 才算（缺＝當成 '
                                'legacy／原句）。"""\n'
                                '    try:\n'
                                '        return st.session_state.get(_NAV4_LEGACY_SESSION_KEY) is '
                                'False\n'
                                '    except Exception:  # noqa: BLE001 — 無 session 環境（純單元測試）⇒ 原句\n'
                                '        return False\n'
                                '\n'
                                '\n'
                                'def _mode_text(text: str) -> str:\n'
                                '    """送進畫面前的最後一道：預設模式把「切回舊版」類指路句換成誠實句；其餘模式原樣返回。"""\n'
                                '    if not _in_default_nav():\n'
                                '        return text\n'
                                '    return (text.replace(ia_nav.CONTENT_EDIT_OLD_UI_WHERE, '
                                'DEFAULT_MODE_NOT_YET)\n'
                                '                .replace(_V2_OLD_UI, '
                                'DEFAULT_MODE_NOT_YET_SHORT))\n'
                                '_V2_FILL_LOTS: str = ("把持股的張數與均價補齊" + V2_EXCERPT_GAP + _V2_OLD_UI '
                                '+ V2_EXCERPT_GAP\n',
                                '_V2_OLD_UI: str = "目前請切回舊版 → 📁 組合管理"   # 客戶原句的開頭一段（K1：原文摘錄）\n'
                                '_V2_FILL_LOTS: str = ("把持股的張數與均價補齊" + V2_EXCERPT_GAP + _V2_OLD_UI '
                                '+ V2_EXCERPT_GAP\n'),
                               ('    try:\n'
                                '        _html = _V2_BLANK_LINE_RE.sub("\\n", '
                                '_mode_text(v2_card_html(card, facts, signal_text)))\n'
                                "        st.markdown(f'<div "
                                'class="{V2_HOLD_CARD_CLASS}">{_html}</div>\',\n',
                                '    try:\n'
                                '        _html = _V2_BLANK_LINE_RE.sub("\\n", v2_card_html(card, '
                                'facts, signal_text))\n'
                                "        st.markdown(f'<div "
                                'class="{V2_HOLD_CARD_CLASS}">{_html}</div>\',\n'),
                               ('    # 👤 我的 P1（D 段）：~~「**唯讀** —— 要新增／修改／刪除請到既有的 📁 組合管理分頁。」~~\n'
                                '    st.caption(_mode_text("**唯讀** —— " + '
                                '_edit_where("要新增／修改／刪除持股"))\n'
                                '               + f"要換 '
                                'Sheet、選組合：到{ia_nav.where_to_find(ia_nav.PAGE_ME)}。")\n',
                                '    # 👤 我的 P1（D 段）：~~「**唯讀** —— 要新增／修改／刪除請到既有的 📁 組合管理分頁。」~~\n'
                                '    st.caption("**唯讀** —— " + _edit_where("要新增／修改／刪除持股")\n'
                                '               + f"要換 '
                                'Sheet、選組合：到{ia_nav.where_to_find(ia_nav.PAGE_ME)}。")\n')),
 'src/ui/views/page_market.py': (('\n'
                                  '# '
                                  '══════════════════════════════════════════════════════════════════\n'
                                  '# NAV-1 回修（QA MAJOR-1）：預設（新四頁）模式的頁內文字 —— 不得叫使用者去一個畫面上不存在的地方\n'
                                  '# '
                                  '══════════════════════════════════════════════════════════════════\n'
                                  '# 預設模式下（`app.py` 在 session 明確寫 `_nav4_legacy = '
                                  'False`），舊版入口（側欄「不使用」radio、舊頁籤）與\n'
                                  '# 「🚦 今天」「📖 憑什麼」頁對一般使用者**不存在**（DEC-097）；本頁原本寫給 D2 殼的指路句因此成了死路。\n'
                                  '# 做法（⚠️ 有意識的修改，⛔ 不是漏刪）：**只在呈現層**依 session 旗標分模式 ——\n'
                                  '#   · legacy 模式（旗標為 True）或旗標不存在（單元測試／直接呼叫）：輸出**原句逐字不變**；\n'
                                  '#   · 預設模式（旗標明確為 False）：改成不指向 legacy 的誠實句，或略去（不新增任何 UI 元件、不放任何 '
                                  'legacy 連結）。\n'
                                  '# 原常數一字未改。⚠️ 本批**不改** `where_to_find` 產生的路徑名（牽動 ia_nav 46 字上限與 '
                                  'revert chain，併 I-1 另批）。\n'
                                  '# ⚠️ 旗標 key 的字面值與 `shared/ia_nav4.LEGACY_SESSION_KEY` 各一份（本檔不得 '
                                  'import ia_nav4：legacy 路徑零依賴新模組；\n'
                                  '#    相等由 `tests/test_nav1_default_mode_text.py` 釘住）。\n'
                                  '_NAV4_LEGACY_SESSION_KEY: str = "_nav4_legacy"\n'
                                  'DEFAULT_MODE_NOT_YET: str = "新版尚未提供，後續批次處理"\n'
                                  '\n'
                                  '\n'
                                  'def _in_default_nav() -> bool:\n'
                                  '    """預設（新四頁）模式？只有 session 旗標**明確為 False** 才算（缺＝當成 '
                                  'legacy／原句）。"""\n'
                                  '    try:\n'
                                  '        return st.session_state.get(_NAV4_LEGACY_SESSION_KEY) '
                                  'is False\n'
                                  '    except Exception:  # noqa: BLE001 — 無 session 環境（純單元測試）⇒ '
                                  '原句\n'
                                  '        return False\n'
                                  '\n'
                                  '\n'
                                  'def _old_ui_pointer() -> str:\n'
                                  '    return DEFAULT_MODE_NOT_YET if _in_default_nav() else '
                                  'OLD_UI_POINTER\n'
                                  '\n'
                                  '\n'
                                  'def _x3_text() -> str:\n'
                                  '    """X3 說明；預設模式拿掉指向「🚦 今天」頁的括號（那一頁在預設導覽不存在）。"""\n'
                                  '    return X3_TEXT.replace("（與「🚦 今天」頁同一段程式）", "") if '
                                  '_in_default_nav() else X3_TEXT\n'
                                  '\n'
                                  '#: 位階契約 `source`（分支識別碼，SSOT `shared.regime_arbiter.SOURCE_*`）→ '
                                  '人話。\n',
                                  '\n'
                                  '#: 位階契約 `source`（分支識別碼，SSOT `shared.regime_arbiter.SOURCE_*`）→ '
                                  '人話。\n'),
                                 ('        return ("本次使用中還沒按過更新，所以還沒有更新報告；"\n'
                                  '                "按頁首的更新鈕後，報告會出現在更新鈕下方" + ("。" if '
                                  '_in_default_nav() else "（與「🚦 今天」頁同一份）。"))\n'
                                  '    return ("本次更新的逐來源結果見頁首更新鈕下方「上一次更新的結果」"\n'
                                  '            + ("。" if _in_default_nav() else "（與「🚦 '
                                  '今天」頁同一份報告）。"))\n'
                                  '\n',
                                  '        return ("本次使用中還沒按過更新，所以還沒有更新報告；"\n'
                                  '                "按頁首的更新鈕後，報告會出現在更新鈕下方（與「🚦 今天」頁同一份）。")\n'
                                  '    return "本次更新的逐來源結果見頁首更新鈕下方「上一次更新的結果」（與「🚦 今天」頁同一份報告）。"\n'
                                  '\n'),
                                 ('    _render_raw_table(raw_rows(session, X6_FIELDS), '
                                  'empty_text="")\n'
                                  '    st.caption(f"全球資金流向、全球風險雷達本批未接到本頁（{_old_ui_pointer()}）；"\n'
                                  '               "雙速合議、Risk-on／off 標籤、中國拖累不在本頁。")\n',
                                  '    _render_raw_table(raw_rows(session, X6_FIELDS), '
                                  'empty_text="")\n'
                                  '    st.caption(f"全球資金流向、全球風險雷達本批未接到本頁（{OLD_UI_POINTER}）；"\n'
                                  '               "雙速合議、Risk-on／off 標籤、中國拖累不在本頁。")\n'),
                                 ('            st.caption("\u3000·\u3000".join(f"{_c}：{_n}" for '
                                  '_c, _n in LEADING_COLUMNS if _n and _c in _keep))\n'
                                  '    '
                                  'st.caption(f"外資連續買賣超天數、熱錢三角、融券本批未接到本頁；{_old_ui_pointer()}。")\n'
                                  '\n',
                                  '            st.caption("\u3000·\u3000".join(f"{_c}：{_n}" for '
                                  '_c, _n in LEADING_COLUMNS if _n and _c in _keep))\n'
                                  '    st.caption(f"外資連續買賣超天數、熱錢三角、融券本批未接到本頁；{OLD_UI_POINTER}。")\n'
                                  '\n'),
                                 ('    st.markdown(status_line(_report, _danger))\n'
                                  '    st.caption(AS_OF_NOT_PROVIDED if _in_default_nav() else\n'
                                  '               f"{AS_OF_NOT_PROVIDED}｜🩺 資料健康：請到 "\n'
                                  '               '
                                  'f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")\n',
                                  '    st.markdown(status_line(_report, _danger))\n'
                                  '    st.caption(f"{AS_OF_NOT_PROVIDED}｜🩺 資料健康：請到 "\n'
                                  '               '
                                  'f"{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}")\n'),
                                 ('    with st.expander(X3_TITLE, expanded=False):\n'
                                  '        st.markdown(_x3_text())\n'
                                  '    with st.expander("指標明細（16 項）", expanded=False):\n',
                                  '    with st.expander(X3_TITLE, expanded=False):\n'
                                  '        st.markdown(X3_TEXT)\n'
                                  '    with st.expander("指標明細（16 項）", expanded=False):\n'),
                                 ('                          '
                                  'empty_text=f"{MISSING}：本次使用中還沒有總經資料。")\n'
                                  '        st.caption(f"景氣拐點六大面向本批未接到本頁；{_old_ui_pointer()}。")\n'
                                  '    with st.expander("籌碼（原始資料）", expanded=False):\n',
                                  '                          '
                                  'empty_text=f"{MISSING}：本次使用中還沒有總經資料。")\n'
                                  '        st.caption(f"景氣拐點六大面向本批未接到本頁；{OLD_UI_POINTER}。")\n'
                                  '    with st.expander("籌碼（原始資料）", expanded=False):\n'),
                                 ('            f"- {report_pointer(_report)}\\n"\n'
                                  '            + ("" if _in_default_nav() else\n'
                                  '               f"- '
                                  '各來源的健康狀態與根因：{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}。\\n")\n'
                                  '            + "- ⚠️ '
                                  '揭露：更新報告的「系統風險上限」步驟說明會列出本次寫檔的數值（現行行為，本批不改）。")\n'
                                  '    with st.expander("問 AI／查看依據", expanded=False):\n',
                                  '            f"- {report_pointer(_report)}\\n"\n'
                                  '            f"- '
                                  '各來源的健康狀態與根因：{ia_nav.where_to_find(ia_nav.SECTION_WHY_DATA_HEALTH)}。\\n"\n'
                                  '            "- ⚠️ 揭露：更新報告的「系統風險上限」步驟說明會列出本次寫檔的數值（現行行為，本批不改）。")\n'
                                  '    with st.expander("問 AI／查看依據", expanded=False):\n'),
                                 ('    with st.expander("問 AI／查看依據", expanded=False):\n'
                                  '        if _in_default_nav():\n'
                                  '            st.markdown(f"AI 問答：{DEFAULT_MODE_NOT_YET}。")\n'
                                  '        else:\n'
                                  '            st.markdown(f"AI 問答請到 '
                                  '{ia_nav.where_to_find(ia_nav.SECTION_WHY_QA)}"\n'
                                  '                        "（沿用既有 AI 問答，本頁不另開一套）。")\n',
                                  '    with st.expander("問 AI／查看依據", expanded=False):\n'
                                  '        st.markdown(f"AI 問答請到 '
                                  '{ia_nav.where_to_find(ia_nav.SECTION_WHY_QA)}"\n'
                                  '                    "（沿用既有 AI 問答，本頁不另開一套）。")\n')),
 'src/ui/views/page_me.py': (('# '
                              '══════════════════════════════════════════════════════════════════\n'
                              '# NAV-1 回修（QA MAJOR-1）：預設（新四頁）模式的頁內文字 —— 不得叫使用者去一個畫面上不存在的地方\n'
                              '# '
                              '══════════════════════════════════════════════════════════════════\n'
                              '# 預設模式下（`app.py` 在 session 明確寫 `_nav4_legacy = '
                              'False`），舊版入口（側欄「不使用」radio、舊頁籤）對一般使用者\n'
                              '# **不存在**（DEC-097：legacy 入口不得出現在一般導覽）；本頁原本寫給 D2 '
                              '殼的「切回舊版…」類指路句因此成了死路。\n'
                              '# 做法（⚠️ 有意識的修改，⛔ 不是漏刪）：**只在呈現層**依 session 旗標分模式 ——\n'
                              '#   · legacy 模式（旗標為 True）或旗標不存在（單元測試／直接呼叫）：輸出**原句逐字不變**；\n'
                              '#   · 預設模式（旗標明確為 False）：改成不指向 legacy 的誠實句（「新版尚未提供，後續批次處理」）或略去。\n'
                              '# 原常數（含 `shared/ia_nav.CONTENT_EDIT_OLD_UI_WHERE`）一字未改；本批**不改** '
                              '`where_to_find` 產生的路徑名\n'
                              '# （🛡️持股›…、📊 大盤›🚦 今天、🩺／📖 —— 牽動 ia_nav 46 字上限與 revert chain，併 I-1 '
                              '另批）。\n'
                              '# ⚠️ 旗標 key 的字面值與 `shared/ia_nav4.LEGACY_SESSION_KEY` 各一份（本檔不得 '
                              'import ia_nav4：legacy 路徑零依賴新模組；\n'
                              '#    相等由 `tests/test_nav1_default_mode_text.py` 釘住）。\n'
                              '_NAV4_LEGACY_SESSION_KEY: str = "_nav4_legacy"\n'
                              '#: 預設模式下取代「客戶原句／切回舊版」的誠實句（不含任何 legacy 字樣）。\n'
                              'DEFAULT_MODE_NOT_YET: str = "此功能新版尚未提供，後續批次處理。"\n'
                              '\n'
                              '\n'
                              'def _in_default_nav() -> bool:\n'
                              '    """預設（新四頁）模式？只有 session 旗標**明確為 False** 才算（缺＝當成 '
                              'legacy／原句，保護既有單元測試與直接呼叫）。"""\n'
                              '    try:\n'
                              '        return st.session_state.get(_NAV4_LEGACY_SESSION_KEY) is '
                              'False\n'
                              '    except Exception:  # noqa: BLE001 — 無 session 環境（純單元測試）⇒ 原句\n'
                              '        return False\n'
                              '\n'
                              '\n'
                              '# '
                              '══════════════════════════════════════════════════════════════════\n'
                              '# 首屏字樣（卡名 ＝ `ia_nav.SECTION_LABELS`，指路句與卡名同一個 SSOT）\n',
                              '# '
                              '══════════════════════════════════════════════════════════════════\n'
                              '# 首屏字樣（卡名 ＝ `ia_nav.SECTION_LABELS`，指路句與卡名同一個 SSOT）\n'),
                             ('# '
                              '══════════════════════════════════════════════════════════════════\n'
                              '\n'
                              '\n'
                              'PAGE_QUESTION: str = "我用哪個 Google 帳號、這個 App 現在讀哪一本 Sheet、這本 Sheet '
                              '裡分析的是哪一本？"\n',
                              '# '
                              '══════════════════════════════════════════════════════════════════\n'
                              'PAGE_QUESTION: str = "我用哪個 Google 帳號、這個 App 現在讀哪一本 Sheet、這本 Sheet '
                              '裡分析的是哪一本？"\n'),
                             ('EDIT_CONTENT_WHERE: str = "要新增／修改組合、觀察清單或持股列：" + '
                              'ia_nav.CONTENT_EDIT_OLD_UI_WHERE\n'
                              'EDIT_CONTENT_WHERE_DEFAULT_MODE: str = "要新增／修改組合、觀察清單或持股列：" + '
                              'DEFAULT_MODE_NOT_YET\n'
                              'CREATE_SHEET_WHERE_DEFAULT_MODE: str = "要建立新 Sheet：" + '
                              'DEFAULT_MODE_NOT_YET\n'
                              'USED_BY_HEADING: str = "用到這本 Sheet 的頁"\n',
                              'EDIT_CONTENT_WHERE: str = "要新增／修改組合、觀察清單或持股列：" + '
                              'ia_nav.CONTENT_EDIT_OLD_UI_WHERE\n'
                              'USED_BY_HEADING: str = "用到這本 Sheet 的頁"\n'),
                             (')\n'
                              '#: 預設（新四頁）模式：不列預設導覽到不了的頁（🚦 今天、⚡ 行動），只列四頁導覽內的兩頁。\n'
                              'USED_BY_LINES_DEFAULT_MODE: tuple[str, ...] = USED_BY_LINES[:2]\n'
                              '\n',
                              ')\n\n'),
                             ('                         '
                              'f"「{OLD_UI_TAB}」。舊版的頁籤照舊讀它自己的設定，不受本頁的組合／觀察清單選定影響。")\n'
                              '#: 預設（新四頁）模式的「已知限制」：不提側欄「不使用」（那個控制項在這個模式不存在）。\n'
                              'KNOWN_LIMITS_DEFAULT_MODE: tuple[str, ...] = (\n'
                              '    "組合／觀察清單的選定只記在這一次使用中：重新整理頁面、或重新登入之後要重選（不會寫進你的 Sheet 或網址）。",\n'
                              '    "Google 登入轉跳回來是新的一次使用：頁面會回到起始頁，登入後請再到「" + '
                              'ia_nav.page_label(ia_nav.PAGE_ME) + "」。",\n'
                              '    "同時開多個瀏覽器分頁時，每個分頁依自己的網址還原 Sheet；在這裡登出只管得到目前這個分頁。",\n'
                              '    "排程推播讀的是部署環境的設定，與本頁選哪一本無關。",\n'
                              ')\n'
                              'DETAIL_TITLE_DEFAULT_MODE: str = "▸ 詳細：已知限制"\n'
                              'KNOWN_LIMITS: tuple[str, ...] = (\n',
                              '                         '
                              'f"「{OLD_UI_TAB}」。舊版的頁籤照舊讀它自己的設定，不受本頁的組合／觀察清單選定影響。")\n'
                              'KNOWN_LIMITS: tuple[str, ...] = (\n'),
                             ('            _lines.append(WL_SELECTED.format(name=_md(_wl_sel)))\n'
                              '    return CardView(CARD_CONTENT_TITLE, _lines[0], '
                              'lines=tuple(_lines[1:]),\n'
                              '                    captions=(EDIT_CONTENT_WHERE_DEFAULT_MODE if '
                              '_in_default_nav() else EDIT_CONTENT_WHERE,))\n'
                              '\n',
                              '            _lines.append(WL_SELECTED.format(name=_md(_wl_sel)))\n'
                              '    return CardView(CARD_CONTENT_TITLE, _lines[0], '
                              'lines=tuple(_lines[1:]), captions=(EDIT_CONTENT_WHERE,))\n'
                              '\n'),
                             ('                      type="primary", width="stretch")\n'
                              '        st.caption(CREATE_SHEET_WHERE_DEFAULT_MODE if '
                              '_in_default_nav() else CREATE_SHEET_WHERE)\n'
                              '\n',
                              '                      type="primary", width="stretch")\n'
                              '        st.caption(CREATE_SHEET_WHERE)\n'
                              '\n'),
                             ('    st.markdown(f"**{USED_BY_HEADING}**")\n'
                              '    st.markdown("\\n".join(f"- {_ln}" for _ln in '
                              '(USED_BY_LINES_DEFAULT_MODE if _in_default_nav() else '
                              'USED_BY_LINES)))\n'
                              '\n',
                              '    st.markdown(f"**{USED_BY_HEADING}**")\n'
                              '    st.markdown("\\n".join(f"- {_ln}" for _ln in USED_BY_LINES))\n'
                              '\n'),
                             ('        _render_contents(_contents, logged_in=_logged, '
                              'active_ok=_active_ok)\n'
                              '    if _in_default_nav():\n'
                              '        # 預設（新四頁）模式：沒有「切回舊版」段（那個入口對一般使用者不存在，DEC-097）；限制清單用不指向 '
                              'legacy 的版本。\n'
                              '        with st.expander(DETAIL_TITLE_DEFAULT_MODE, '
                              'expanded=False):\n'
                              '            st.markdown("**已知限制**\\n" + "\\n".join(f"- {_ln}" for '
                              '_ln in KNOWN_LIMITS_DEFAULT_MODE))\n'
                              '        return\n'
                              '    with st.expander(DETAIL_TITLE, expanded=False):\n',
                              '        _render_contents(_contents, logged_in=_logged, '
                              'active_ok=_active_ok)\n'
                              '    with st.expander(DETAIL_TITLE, expanded=False):\n'))}


def _rel(file_path) -> str:
    p = Path(file_path)
    return (p.resolve().relative_to(REPO) if p.is_absolute() else p).as_posix()


def nav1_revert_for(file_path, code: str) -> str:
    """給模組 `__file__`（或 repo 相對路徑）與原始碼，換回 NAV-1 回修之前的寫法（無 pair 則原樣；只套一次）。"""
    rel = _rel(file_path)
    # 📌 XV 客戶裁示批（XV-H3，2026-10-28；有意識的接鏈，⛔ 不是漏改）：本批動了 `src/ui/views/page_hold.py`
    #   （被本節及更舊的鏈管）⇒ 最新的那一批先換回（鏈頭往前接一節；只套一次；⛔ 不動本表與 `NAV1_BASE_SHA`）。
    from tests.test_xvext_revert_chain import xvext_revert_for
    code = xvext_revert_for(rel, code)
    pairs = NAV1_REVERT_PAIRS.get(rel, ())
    if not pairs:
        return code
    counts = [code.count(new) for new, _old in pairs]
    if all(c == 0 for c in counts):
        return code          # 已被前一個掛點換回
    assert all(c == 1 for c in counts), (
        f"{rel} NAV-1 還原組錨點漂移（各組出現次數 {counts}；應全 1 或全 0）—— 須重產還原組")
    for new, old in pairs:
        code = code.replace(new, old)
    return code


def test_nav1_revert_is_exact_base_source():
    for rel in sorted(NAV1_REVERT_PAIRS):
        code = nav1_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == NAV1_BASE_SHA[rel], rel


def test_nav1_revert_is_idempotent():
    for rel in sorted(NAV1_REVERT_PAIRS):
        once = nav1_revert_for(rel, (REPO / rel).read_text(encoding="utf-8"))
        assert nav1_revert_for(rel, once) == once, rel


def test_chain_head_calls_nav1_before_d2():
    """原鏈頭 `sheet_safety_revert_for` 必須先呼叫本節（否則舊批次的基底 sha 守衛看到的是還沒還原的檔）。"""
    import inspect

    from tests.test_sheet_safety_revert_chain import sheet_safety_revert_for
    src = inspect.getsource(sheet_safety_revert_for)
    assert src.index("nav1_revert_for(rel, code)") < src.index("d2_revert_for(rel, code)")
