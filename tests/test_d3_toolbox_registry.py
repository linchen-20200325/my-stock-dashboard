# -*- coding: utf-8 -*-
"""D3 / B7 v19.181 — 🔧 工具箱 + 教學卡 vs 判定式 對帳守衛。

【這批守衛在防什麼】
三個病灶，全部是「畫面說的」與「系統算的」對不上：

  A. 教學卡（`data_registry.EDU_GUIDE`）的門檻**手打**，與判定 SSOT 相反。
     案發實例：融資餘額 2,600 億時 ——
       🌍 總經的融資卡  → 「⚡超過2500億警戒」（黃）
       📚 說明書教學卡  → 「> 2500 億 = 🔴 散戶過熱，注意主力出貨」（紅）
     同一個數字、同一個 app，兩個相反結論。同 block 的 `historical_anchor`
     又手寫「健康區 1500–2000 億」，是第三個版本。

  B. 對帳面板把 `market_regime` 的滿分寫死 4，但真滿分是 4 / 5 / 6
     （ad_ratio、m1b_m2_gap 有傳才加）。max_score=6 時 score_pct 高估 50%
     ⇒ 對帳的輸入本身就是錯的。同段的「3 個對帳」是硬編碼字串。

  C. 資料新鮮度在工具箱裡有三把尺，且都沒有名字、沒說明為何不同：
       health_inspector    daily ≤5 綠、>5 直接紅（無黃燈）、yearly 恆綠
       data_registry_panel FRESHNESS_THRESHOLDS_DAYS (7, 30)
       data_coverage       shared.staleness SSOT (daily 7) + 具名 warn 3
     同一筆落後 6 天的日頻資料，三個子頁同時顯示 🟡 / 🟢 / 🔴。

【設計原則（沿用 B6-a 的教訓，本 session 已被字串掃描守衛的假紅燈擋了 7 次）】
- **優先行為斷言**：能呼叫 production 函式對答案的就不比字串。
  例：`margin_card()` 對 2,600 到底印黃還是紅 —— 直接呼叫它問。
- **要比數字就從 SSOT 取，不要抄常值**。抄常值 = 把同一個數字寫第三份，
  漂移時三份一起錯（守衛照抄實作字面 ⇒ 永遠不會發現實作有問題）。
- **要掃原始碼就用 AST**：ast 天然看不到註解；失敗訊息印 `file:line` + 該行原文。
  本檔只有 **一個** 原始碼掃描守衛（`test_top5_constant_matches_section_chips`），
  且它比對的是**跨兩個檔案的兩份數字**是否一致 —— 不是「實作是否等於它自己」。
"""
from __future__ import annotations

import ast
import contextlib
import datetime as dt
import pathlib
import re

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent


# ══════════════════════════════════════════════════════════════════
# 共用工具
# ══════════════════════════════════════════════════════════════════

@contextlib.contextmanager
def fake_session_state(state: dict):
    """暫時把 `streamlit.session_state` 換成一個普通 dict。

    reconcile_panel 的 `_ss()` 只用到 `.get`，dict 足夠；離開 context 一定還原
    （包含「原本根本讀不到 session_state」的裸跑情境）。
    """
    import streamlit as _st
    _sentinel = object()
    try:
        _old = getattr(_st, 'session_state', _sentinel)
    except Exception:  # noqa: BLE001 — 無 runtime 時存取可能直接 raise
        _old = _sentinel
    _st.session_state = state
    try:
        yield
    finally:
        if _old is _sentinel:
            try:
                delattr(_st, 'session_state')
            except Exception:  # noqa: BLE001
                pass
        else:
            _st.session_state = _old


def _literal_number(node: ast.AST):
    """AST 節點 → 數字字面（含 `-10000` 這種 UnaryOp）；非數字回 None。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        _inner = _literal_number(node.operand)
        return None if _inner is None else -_inner
    return None


def _src_line(path: pathlib.Path, lineno: int) -> str:
    try:
        return path.read_text(encoding='utf-8').splitlines()[lineno - 1].strip()
    except Exception:  # noqa: BLE001
        return '(讀不到原文)'


# ══════════════════════════════════════════════════════════════════
# A. 教學卡門檻 ↔ 判定 SSOT
# ══════════════════════════════════════════════════════════════════

class TestEduCardVsProduction:
    """教學卡宣稱的門檻，必須與畫面上真的會亮的燈同源。"""

    def test_margin_between_warn_and_overheat_is_yellow_in_production(self):
        """行為前提：融資落在「警戒~過熱」之間（如 user 舉的 2,600 億）
        在 production 是**黃燈**，不是紅。

        這條先釘住「事實」，下一條才有意義 —— 否則教學卡改對了、
        production 卻悄悄改了門檻，兩邊會一起錯而測試不知道。
        """
        from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
        from shared.signal_thresholds import (
            MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
            MARGIN_BALANCE_WARN_THRESHOLD_YI,
        )
        from src.ui.render.macro_ui_components import margin_card

        assert MARGIN_BALANCE_WARN_THRESHOLD_YI < MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI, (
            '前提失效：警戒線應低於過熱線')
        _probe = (MARGIN_BALANCE_WARN_THRESHOLD_YI
                  + MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI) / 2.0   # 警戒~過熱正中間
        _html = margin_card(_probe)
        assert TRAFFIC_YELLOW in _html, (
            f'融資 {_probe:.0f} 億落在警戒帶，production 融資卡應為黃燈，實際 HTML：\n{_html}')
        assert TRAFFIC_RED not in _html, (
            f'融資 {_probe:.0f} 億尚未達過熱紅線 '
            f'{MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:.0f}，不該是紅燈。')
        assert TRAFFIC_GREEN not in _html, (
            f'融資 {_probe:.0f} 億已越過警戒線 '
            f'{MARGIN_BALANCE_WARN_THRESHOLD_YI:.0f}，不該是綠燈。')

    def test_margin_edu_card_red_line_is_overheat_not_warn(self):
        """教學卡的 🔴 那一列，門檻必須是**過熱線**（3400）而非警戒線（2500）。

        這正是 B7 回報的 bug：舊文案寫「> 2500 億 = 🔴 散戶過熱」，
        於是 2,600 億時畫面黃、教學卡紅。

        比對方式：從 SSOT 常數格式化出期望字串再找，**不抄常值**。
        """
        from shared.edu_tokens import edu_tokens, resolve_edu_rules
        from shared.signal_thresholds import (
            MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
            MARGIN_BALANCE_WARN_THRESHOLD_YI,
        )
        from src.data.core.data_registry import EDU_GUIDE

        _rules = resolve_edu_rules(EDU_GUIDE['MI_MARGN']['how_to_read'], edu_tokens())
        _red = [cond for cond, verdict in _rules if verdict.startswith('🔴')]
        assert len(_red) == 1, f'MI_MARGN 教學卡應恰有 1 條 🔴 規則，實際 {len(_red)}：{_red}'
        _warn_s = f'{MARGIN_BALANCE_WARN_THRESHOLD_YI:,.0f}'
        _over_s = f'{MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI:,.0f}'
        assert _over_s in _red[0], (
            f'🔴 規則的門檻必須是過熱線 {_over_s}，實際條件字串：{_red[0]!r}')
        assert _warn_s not in _red[0], (
            f'🔴 規則不得用警戒線 {_warn_s} 當門檻 —— 那會讓 '
            f'{_warn_s}~{_over_s} 這段在教學卡上是紅、在畫面上是黃。'
            f'實際條件字串：{_red[0]!r}')

    def test_margin_edu_card_thresholds_are_exactly_the_two_ssot_lines(self):
        """教學卡 3 條水位規則裡出現的**億元數字集合** == SSOT 的兩條線。

        可證偽性：任何人再手寫一個「1500」「2200」進去就會紅。
        且測試從常數取值，改門檻時測試自動跟上（不是抄第三份）。
        """
        from shared.edu_tokens import edu_tokens, resolve_edu_rules
        from shared.signal_thresholds import (
            MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
            MARGIN_BALANCE_WARN_THRESHOLD_YI,
        )
        from src.data.core.data_registry import EDU_GUIDE

        _rules = resolve_edu_rules(EDU_GUIDE['MI_MARGN']['how_to_read'], edu_tokens())
        _conds = ' '.join(cond for cond, _ in _rules)
        _nums = {int(_n.replace(',', ''))
                 for _n in re.findall(r'\d[\d,]{2,}', _conds)}
        _expect = {int(MARGIN_BALANCE_WARN_THRESHOLD_YI),
                   int(MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI)}
        assert _nums == _expect, (
            f'MI_MARGN 教學卡的門檻數字 {sorted(_nums)} 與 SSOT {sorted(_expect)} 不符。\n'
            f'規則原文：{_rules}')

    def test_tokenized_cards_have_no_bare_numbers_in_threshold_column(self):
        """已 token 化的教學卡，**門檻欄**（how_to_read 的第一欄）不得有裸數字。

        為什麼查「原文」而不是查「算出來的值」：這條守的是**寫法** ——
        只要有人手打數字，之後就會漂移。門檻欄一律走 SSOT token。

        為什麼**只查門檻欄、不查判讀欄**：判讀欄是散文，合法地含年份
        （「2022/10、2023/10 雙頂歷史」）、歷史高點等非門檻數字。
        把它們一起掃會製造假紅燈，而假紅燈只會讓人把守衛刪掉。
        門檻是否手打，看門檻欄就夠了。

        ⚠️ 已知覆蓋範圍：regex 最短匹配 3 個字元，故只抓 100 以上（含千分位）的數字。
        兩位數的手打門檻（如 VIX 的 22 / 30）抓不到 —— 這是**刻意的取捨**：
        兩位數在中文散文裡太常見，全抓會製造假紅燈。B7 回報的漂移全是 3 位數以上。
        """
        from src.data.core.data_registry import EDU_GUIDE

        #: 已 token 化、門檻欄必須零裸數字的 EDU key
        _TOKENIZED = ('MI_MARGN', 'DX-Y.NYB', '^TNX', '^VIX', 'CPILFESL',
                      'XTEXVA01TWM664S', 'ms1.json',
                      '前五大留倉', '前十大留倉', 'BFI82U', 'BWIBBU_d')

        _bad: list[str] = []
        for _key in _TOKENIZED:
            _edu = EDU_GUIDE.get(_key)
            assert _edu is not None, f'EDU_GUIDE 少了 {_key}，測試清單需同步更新'
            for _cond, _ in _edu.get('how_to_read', []):
                # 先把 §§TOKEN§§ 拿掉再找數字，避免 token 名裡的數字誤判
                _stripped = re.sub(r'§§[A-Z0-9_]+§§', '', str(_cond))
                for _n in re.findall(r'\d[\d,]{2,}', _stripped):
                    _bad.append(f'{_key}: 門檻欄 {_cond!r} → 裸數字 {_n}')
        assert not _bad, (
            '下列教學卡的門檻欄仍有手打數字（應改寫成 §§TOKEN§§，'
            'token 清單見 shared.edu_tokens.edu_tokens）：\n  ' + '\n  '.join(_bad))

    def test_no_unresolved_tokens_anywhere_in_edu_guide(self):
        """全 EDU_GUIDE 不得有「沒登記的 token」—— 否則畫面會印出 `§§XXX§§` 亂碼。

        `resolve_edu_tokens` 刻意讓未登記 token 原樣顯示（§1 降級不靜默），
        本測試負責在 CI 就攔下，不必等使用者看到。
        """
        from shared.edu_tokens import unresolved_tokens
        from src.data.core.data_registry import EDU_GUIDE

        _bad = unresolved_tokens(EDU_GUIDE)
        assert not _bad, (
            f'EDU_GUIDE 用了未登記的 token：{sorted(_bad)}。'
            f'請在 shared/edu_tokens.edu_tokens() 補上（值必須來自 L0 SSOT 常數）。')

    def test_all_tokens_resolve_to_real_ssot_values(self):
        """每個 token 都要解得出實值 —— 不得是 `⟪MISSING-...⟫` 錯誤標記。

        `_spec` / `_band` 在查不到 key 時會回一個看得見的標記（而不是 0 或空字串），
        本測試確保那個標記不會真的出現在正式清單裡（= key 打錯 / SSOT 被改名）。
        """
        from shared.edu_tokens import edu_tokens

        _bad = {k: v for k, v in edu_tokens().items() if '⟪MISSING' in v}
        assert not _bad, (
            f'下列 token 對不上 SSOT（很可能 macro_buckets 的 spec key 被改名）：{_bad}')

    def test_rendered_card_html_has_no_raw_tokens(self):
        """行為終點：`render_edu_card_html()` 的輸出不得殘留 `§§`。

        直接跑 render，涵蓋所有 registry 對得上的教學卡。
        """
        from src.data.core import get_by_category, get_categories, get_edu
        from src.data.core.data_registry import render_edu_card_html

        _leaks: list[str] = []
        for _cat in get_categories():
            for _e in get_by_category(_cat):
                _edu = get_edu(_e.get('identifier'))
                if _edu is None:
                    continue
                _html = render_edu_card_html(_e, _edu)
                if '§§' in _html:
                    _leaks.append(f"{_e.get('identifier')}: "
                                  f"{re.findall(r'§§[A-Z0-9_]*§§', _html)}")
        assert not _leaks, '下列教學卡渲染後仍有未取代的 token：\n  ' + '\n  '.join(_leaks)

    def test_top10_card_declares_no_thresholds(self):
        """「前十大留倉」全站無判定式 → 教學卡不得宣稱任何自己的門檻。

        行為前提先驗證：`li_latest` 的「前十大留倉」欄沒有任何 production 判定
        （只出現在表格顯示與凍結偵測監看欄）。這裡用 AST 掃 section_chips
        確認沒有以它為 left 的比較式。
        """
        _path = _ROOT / 'src/ui/tabs/macro/section_chips.py'
        _tree = ast.parse(_path.read_text(encoding='utf-8'))
        _cmps = [
            _n.lineno for _n in ast.walk(_tree)
            if isinstance(_n, ast.Compare)
            and isinstance(_n.left, ast.Name)
            and _n.left.id in ('_top10', '_top_ten')
        ]
        assert not _cmps, (
            '前提失效：section_chips 現在對「前十大留倉」有判定式了 '
            f'(line {_cmps})，教學卡應同步補上對應門檻，而不是繼續寫「不亮燈」。\n'
            + '\n'.join(f'  {_path.name}:{ln}: {_src_line(_path, ln)}' for ln in _cmps))

        from shared.edu_tokens import edu_tokens, resolve_edu_rules
        from src.data.core.data_registry import EDU_GUIDE

        _rules = resolve_edu_rules(EDU_GUIDE['前十大留倉']['how_to_read'], edu_tokens())
        _colored = [c for c, v in _rules
                    if v.startswith(('🟢', '🟡', '🟠', '🔴')) and '前五大' not in c]
        assert not _colored, (
            f'「前十大留倉」沒有任何判定式，教學卡卻宣稱會亮燈：{_colored}。'
            f'（舊版那 4 條線是從「外資期貨」搬來的，同數字不同義。）')

    def test_registry_and_edu_do_not_mention_dead_yield_screener_module(self):
        """文案不得再導引「💎 高息網」模組 —— 它已不存在。

        先驗前提：`yield_screener` 模組沒有 `render_yield_screener`
        （該檔現在只剩 fetcher helper，分頁真名是「🔭 選股網」）。
        """
        from src.ui.tabs import yield_screener as _ys
        assert not hasattr(_ys, 'render_yield_screener'), (
            '前提失效：`render_yield_screener` 又出現了 —— '
            '若「高息網」模組復活，請改回本測試而不是刪掉它。')

        from src.data.core.data_registry import DATA_REGISTRY, EDU_GUIDE

        _hits: list[str] = []
        for _e in DATA_REGISTRY:
            for _f in ('usage', 'name', 'endpoint'):
                if '高息網' in str(_e.get(_f, '')):
                    _hits.append(f"DATA_REGISTRY[{_e.get('identifier')}].{_f}")
        _dump = repr(EDU_GUIDE)
        if '高息網' in _dump:
            _hits.append('EDU_GUIDE（教學卡內文）')
        assert not _hits, (
            '下列文案仍在導引不存在的「💎 高息網」模組（真名為「🔭 選股網」）：\n  '
            + '\n  '.join(_hits))

    def test_top5_constant_matches_section_chips(self):
        """跨檔漂移守衛（本檔**唯一**的原始碼掃描）。

        `shared/signal_thresholds.TOP5_LARGE_TRADER_NET_*` 是 D3 為了讓教學卡
        不再手打數字而抽出來的；`section_chips` 的計分器目前仍是 inline 字面
        （把它改成 import 常數屬 🌍 總經的施工範圍，不在 D3 批次內）。
        本測試盯著兩邊的數字別漂開。

        ⚠️ 若哪天 section_chips 真的改成 import 常數 → 掃不到字面 → **本測試自動放行**
        （那是正確的收斂方向，不該被守衛擋住）。
        """
        from shared.signal_thresholds import (
            TOP5_LARGE_TRADER_NET_BULL_LOTS,
            TOP5_LARGE_TRADER_NET_WARN_LOTS,
        )
        _path = _ROOT / 'src/ui/tabs/macro/section_chips.py'
        _tree = ast.parse(_path.read_text(encoding='utf-8'))
        _found: list[tuple[int, float]] = []
        for _n in ast.walk(_tree):
            if not (isinstance(_n, ast.Compare)
                    and isinstance(_n.left, ast.Name)
                    and _n.left.id == '_top5'):
                continue
            for _c in _n.comparators:
                _v = _literal_number(_c)
                if _v is not None:
                    _found.append((_n.lineno, _v))
        if not _found:
            pytest.skip('section_chips 的 _top5 判定已不用字面數字（很可能已改引常數），'
                        '本漂移守衛無事可做。')
        _nums = {v for _, v in _found}
        _expect = {float(TOP5_LARGE_TRADER_NET_WARN_LOTS),
                   float(TOP5_LARGE_TRADER_NET_BULL_LOTS)}
        assert {float(x) for x in _nums} == _expect, (
            f'`section_chips` 的前五大判定門檻 {sorted(_nums)} 與 '
            f'`signal_thresholds.TOP5_LARGE_TRADER_NET_*` {sorted(_expect)} 不一致；'
            f'教學卡吃的是常數，兩邊漂開 = 教學卡又開始說謊。\n'
            + '\n'.join(f'  {_path.name}:{ln}: {_src_line(_path, ln)}'
                        for ln, _ in _found))


# ══════════════════════════════════════════════════════════════════
# B. 對帳面板：滿分不再寫死 4；caption 不再寫死 3
# ══════════════════════════════════════════════════════════════════

class TestReconcilePanelScorePct:

    @pytest.mark.parametrize('mkt, expected', [
        ({'score': 3, 'max_score': 4}, 75.0),    # 預設模式（只有固定 4 項）
        ({'score': 3, 'max_score': 5}, 60.0),    # 多傳 ad_ratio
        ({'score': 3, 'max_score': 6}, 50.0),    # ad_ratio + m1b_m2 皆傳
        ({'score': 3}, 75.0),                    # 無 max_score → fallback 4（同 macro_helpers）
        ({'score': 6, 'max_score': 4}, 100.0),   # clamp：不得超過 100
        ({'score': 0, 'max_score': 6}, 0.0),
    ])
    def test_score_pct_uses_real_max_score(self, mkt, expected):
        """`score_pct = min(score / max_score × 100, 100)`，分母吃 `mkt_info['max_score']`。

        舊碼寫死 `/ 4.0`：max_score=6 時算出 75 而非 50 —— **高估 50%**，
        對帳面板拿一個假的輸入去對帳。
        """
        from src.ui.pages.reconcile_panel import _get_health_params

        with fake_session_state({'mkt_info': mkt, 'jingqi_info': {'avg': 60}}):
            _jq, _pct, _fnet = _get_health_params()
        assert _pct == pytest.approx(expected), (
            f'mkt_info={mkt} → score_pct 應為 {expected}，實際 {_pct}')

    @pytest.mark.parametrize('falsy_max', [None, 0, 0.0])
    def test_falsy_max_score_mirrors_production_fallback(self, falsy_max):
        """`max_score` 為 falsy（None / 0）→ 退 4.0 分母，與 production **完全一致**。

        production 寫的是 `float(_mkt.get('max_score') or 4.0)`，`or` 對 0 也生效。
        面板刻意抄同一個行為 —— 對帳面板的職責是「把 production 算過的帳再算一次」，
        不是在這裡順手把 0 改判成錯誤。真要改 0 的語意，兩邊一起改。
        """
        from src.ui.pages.reconcile_panel import _get_health_params

        with fake_session_state({'mkt_info': {'score': 3, 'max_score': falsy_max}}):
            _jq, _pct, _fnet = _get_health_params()
        assert _pct == pytest.approx(75.0), (
            f'max_score={falsy_max!r}（falsy）應與 production 一樣退 4.0 分母 → 75.0，'
            f'實際 {_pct}')

    @pytest.mark.parametrize('bad_max', [-4, -0.5, 'x', [1]])
    def test_impossible_max_score_returns_none_not_a_guess(self, bad_max):
        """§1：分母是負數 / 非數字 → 誠實回 None（面板顯示 ⬜），不硬算。

        `market_regime` 的 `_max = 4.0 + 0/1 + 0/1` 結構上不可能為負，
        出現即代表 session 被汙染；硬算會讓一個負的 score_pct 悄悄流進對帳差值。
        """
        from src.ui.pages.reconcile_panel import _get_health_params

        with fake_session_state({'mkt_info': {'score': 3, 'max_score': bad_max}}):
            _jq, _pct, _fnet = _get_health_params()
        assert _pct is None, f'max_score={bad_max!r} 應誠實回 None，實際 {_pct}'

    def test_max_score_really_moves_production_health(self):
        """跨模組行為對帳：max_score 4→6 對 production 健康分的影響量，
        必須等於 `HEALTH_WEIGHT_SCORE × (75 − 50)`。

        這條證明「面板改吃 max_score」不是自嗨 —— production 真的在用它，
        面板不跟就是在對假帳。
        """
        from shared.signal_thresholds import HEALTH_WEIGHT_SCORE
        from src.compute.macro.macro_helpers import calc_traffic_light

        _jq = {'avg': 60.0}
        try:
            _r4 = calc_traffic_light({'score': 3, 'max_score': 4, 'regime': 'neutral'},
                                     _jq, {}, None)
            _r6 = calc_traffic_light({'score': 3, 'max_score': 6, 'regime': 'neutral'},
                                     _jq, {}, None)
        except Exception as _e:  # noqa: BLE001
            pytest.fail(
                f'`calc_traffic_light` 無法以最小輸入執行：{type(_e).__name__}: {_e}。'
                f'本測試靠它證明 max_score 真的會影響 production 健康分 —— '
                f'若簽章變了請同步更新本測試，不要直接刪掉。')
        assert _r4 is not None and _r6 is not None, (
            'calc_traffic_light 以最小輸入回 None，無法驗證 max_score 效應。')
        assert (_r4['health'] - _r6['health']) == pytest.approx(
            HEALTH_WEIGHT_SCORE * (75.0 - 50.0), abs=0.11), (
            f"max_score 4→6 應讓 health 少 {HEALTH_WEIGHT_SCORE * 25:.1f} 分，"
            f"實際 {_r4['health']} → {_r6['health']}")


class TestReconcileCaption:

    def _row(self, status: str, i: int = 0) -> dict:
        return {'name': f'r{i}', 'status': status,
                'source_a': f'A{i}', 'source_b': f'B{i}'}

    @pytest.mark.parametrize('n', [0, 1, 2, 3, 5])
    def test_caption_count_equals_row_count(self, n):
        """caption 開頭的數字 == `len(rows)`。舊碼寫死「3 個對帳」，與列數脫鉤。"""
        from src.ui.pages.reconcile_panel import reconcile_caption

        _rows = [self._row('agree', i) for i in range(n)]
        _cap = reconcile_caption(_rows)
        assert _cap.startswith(f'{n} 個對帳'), f'rows={n} → caption 開頭應為「{n} 個對帳」：{_cap!r}'

    def test_caption_does_not_index_out_of_range(self):
        """列數 < 3 時不得炸 —— 舊碼寫死 `rows[0]` / `rows[2]`（2 列就 IndexError）。"""
        from src.ui.pages.reconcile_panel import reconcile_caption

        _empty = reconcile_caption([])          # 不得拋例外
        assert _empty.startswith('0 個對帳') and '未觸發 0' in _empty, _empty
        _two = reconcile_caption([self._row('agree', 0), self._row('disagree', 1)])
        assert _two.startswith('2 個對帳') and 'A0 vs B0' in _two, _two

    def test_caption_tallies_sum_to_row_count(self):
        """三個計數加總 == 列數（同一段 caption 的多個數字彼此相容）。"""
        from src.ui.pages.reconcile_panel import reconcile_caption

        _rows = [self._row('agree', 0), self._row('disagree', 1),
                 self._row('a_missing', 2), self._row('both_missing', 3)]
        _cap = reconcile_caption(_rows)
        _total = int(re.search(r'^(\d+) 個對帳', _cap).group(1))
        _agree = int(re.search(r'一致 (\d+)', _cap).group(1))
        _dis = int(re.search(r'不一致 (\d+)', _cap).group(1))
        _mis = int(re.search(r'未觸發 (\d+)', _cap).group(1))
        assert (_agree, _dis, _mis) == (1, 1, 2), _cap
        assert _agree + _dis + _mis == _total == len(_rows), _cap
        # both_missing 的來源不列（兩源都沒觸發，印出來只是雜訊）
        assert 'A3 vs B3' not in _cap, f'both_missing 的來源不該列出：{_cap!r}'

    def test_real_rows_render_without_session_state(self):
        """`compute_reconcile_rows()` 在空 session 下也要能算（面板不得因此炸）。"""
        from src.ui.pages.reconcile_panel import compute_reconcile_rows, reconcile_caption

        with fake_session_state({}):
            _rows = compute_reconcile_rows()
        assert _rows, 'compute_reconcile_rows 不該回空 list'
        assert reconcile_caption(_rows).startswith(f'{len(_rows)} 個對帳')


# ══════════════════════════════════════════════════════════════════
# C. 新鮮度三把尺
# ══════════════════════════════════════════════════════════════════

def _date_with_lag(today: dt.date, lag: int) -> str:
    """回一個「距預期最新交易日剛好 lag 天」的日期字串（與星期幾無關）。"""
    from shared.staleness import expected_latest_trading_day
    return (expected_latest_trading_day(today) - dt.timedelta(days=lag)).isoformat()


class TestInspectorFreshness:

    #: 固定基準日，避免測試隨執行當天飄
    TODAY = dt.date(2026, 8, 7)

    def test_lag_helper_is_exact(self):
        """先驗工具本身：`_date_with_lag` 產出的 lag 必須剛好等於指定值。"""
        from shared.staleness import staleness_days
        for _lag in (0, 1, 3, 6, 8, 400):
            assert staleness_days(_date_with_lag(self.TODAY, _lag),
                                  today=self.TODAY) == _lag

    def test_daily_has_a_yellow_band(self):
        """落後 6 天的日頻資料 → 🟡，不再是舊碼的直接 🔴。"""
        from src.ui.pages.health_inspector import freshness_light

        _emoji, _lbl = freshness_light(_date_with_lag(self.TODAY, 6), 'daily',
                                       today=self.TODAY)
        assert _emoji == '🟡', f'lag=6 應為 🟡（舊碼 >5 就紅），實際 {_emoji} / {_lbl}'

    def test_daily_red_line_comes_from_ssot(self):
        """日頻紅線 == `shared.staleness.stale_days_threshold('daily')`。

        邊界兩側都測：門檻當天不紅、多一天才紅。
        """
        from shared.staleness import stale_days_threshold
        from src.ui.pages.health_inspector import freshness_light

        _bad = stale_days_threshold('daily')
        assert freshness_light(_date_with_lag(self.TODAY, _bad), 'daily',
                               today=self.TODAY)[0] != '🔴'
        assert freshness_light(_date_with_lag(self.TODAY, _bad + 1), 'daily',
                               today=self.TODAY)[0] == '🔴'

    def test_daily_fresh_is_green(self):
        from src.ui.pages.health_inspector import freshness_light
        for _lag in (0, 1, 2, 3):
            assert freshness_light(_date_with_lag(self.TODAY, _lag), 'daily',
                                   today=self.TODAY)[0] == '🟢', f'lag={_lag}'

    def test_yearly_is_not_forever_green(self):
        """舊碼 `freq='yearly'` 直接 return 🟢，不看 age —— 停止配息 7 年也綠。"""
        from src.ui.pages.health_inspector import freshness_light

        assert freshness_light(_date_with_lag(self.TODAY, 200), 'yearly',
                               today=self.TODAY)[0] == '🟢', '一年內的年頻資料仍應綠'
        assert freshness_light(_date_with_lag(self.TODAY, 2500), 'yearly',
                               today=self.TODAY)[0] == '🔴', \
            '距今 7 年的年頻資料必須紅 —— 這是舊碼最明顯的說謊處'

    def test_static_never_expires(self):
        """`static`（經理人姓名 / 到職日）只有「抓到 / 沒抓到」，不隨時間過期。

        舊碼會 fall-through 到日頻規則：一位在職 3 年的經理人被標
        「1,100天前 ⚠️ 🔴」並列進「⚠️ 資料異常清單」—— 任期長被當成資料過期。
        """
        from src.ui.pages.health_inspector import FREQ_STATIC, freshness_light

        assert freshness_light(_date_with_lag(self.TODAY, 1100), FREQ_STATIC,
                               today=self.TODAY)[0] == '🟢'
        assert freshness_light(None, FREQ_STATIC, today=self.TODAY)[0] == '🔴'

    def test_missing_and_unparseable_are_red(self):
        from src.ui.pages.health_inspector import freshness_light

        assert freshness_light(None, 'daily', today=self.TODAY) == ('🔴', '未取得')
        assert freshness_light('', 'daily', today=self.TODAY) == ('🔴', '未取得')
        assert freshness_light('not-a-date', 'daily', today=self.TODAY)[0] == '🔴'

    @pytest.mark.parametrize('freq', ['daily', 'monthly', 'quarterly', 'yearly',
                                      'unknown-freq'])
    def test_bands_invariant_warn_le_bad(self, freq):
        """不變量：黃燈起點 ≤ 紅燈起點。

        反過來設 = 黃燈永遠不會出現（靜默失效）。這條也保證同一個函式的
        其他斷言彼此相容：`freshness_light` 對任一 lag 只會有一個答案。
        """
        from src.ui.pages.health_inspector import freshness_bands

        _warn, _bad = freshness_bands(freq)
        assert _warn <= _bad, f'{freq}: warn={_warn} > bad={_bad}'

    @pytest.mark.parametrize('freq', ['daily', 'monthly', 'quarterly', 'yearly'])
    def test_light_is_monotonic_in_lag(self, freq):
        """單調性：lag 越大燈號只會越差，不會忽紅忽綠。"""
        from shared.data_freshness import _FRESH_RANK
        from src.ui.pages.health_inspector import freshness_bands, freshness_light

        _warn, _bad = freshness_bands(freq)
        # 季頻的 warn == bad（刻意無黃燈帶）→ 必須先排序去重，
        # 否則 lag 序列會出現「151 之後又回到 150」，測出來的不是單調性而是我自己的 bug。
        _lags = sorted({0, 1, _warn, _warn + 1, _bad, _bad + 1, _bad + 500})
        _prev, _prev_lag = -1, None
        for _lag in _lags:
            _emoji = freshness_light(_date_with_lag(self.TODAY, _lag), freq,
                                     today=self.TODAY)[0]
            _rank = _FRESH_RANK[_emoji]
            assert _rank >= _prev, (
                f'{freq}: lag {_prev_lag} → {_lag} 燈號竟然變好了（{_emoji}），非單調')
            _prev, _prev_lag = _rank, _lag


class TestFreshnessRulersAgreeOnRedLine:
    """三把尺**不強行統一數值**，但必須守住一條共同底線。

    底線：**任何一頁都不得在超過 SSOT 日頻紅線之後還顯示 🟢**。
    （黃燈起點各頁可以不同 —— 診斷頁本來就該比一般頁嚴格 —— 但「已經過期了還說新鮮」
      不是嚴格程度的差別，是錯。）
    """

    @pytest.mark.parametrize('extra', [1, 2, 10, 25, 100])
    def test_no_page_shows_green_past_ssot_daily_red_line(self, extra):
        from shared.data_freshness import freshness_level_for_cadence
        from shared.staleness import stale_days_threshold
        from src.ui.pages.data_registry_panel import _freshness_emoji
        from src.ui.pages.health_inspector import freshness_light

        _lag = stale_days_threshold('daily') + extra
        _today = dt.date.today()

        _insp = freshness_light(_date_with_lag(_today, _lag), 'daily', today=_today)[0]
        # data_registry_panel 內部用 date.today()，故直接餵日曆天
        _reg = _freshness_emoji((_today - dt.timedelta(days=_lag)).isoformat(),
                                'daily', False)[0]
        _cov = freshness_level_for_cadence(_lag, 'daily', warn_days=3)[0]

        for _name, _emoji in (('health_inspector', _insp),
                              ('data_registry_panel', _reg),
                              ('data_coverage', _cov)):
            assert _emoji != '🟢', (
                f'{_name} 在落後 {_lag} 天（已超過 SSOT 日頻紅線 '
                f'{stale_days_threshold("daily")}）時仍顯示 🟢')


# ══════════════════════════════════════════════════════════════════
# D. 工具箱色票：同一個燈號在每一頁都要同一個顏色
# ══════════════════════════════════════════════════════════════════

class TestToolboxPalette:

    def test_panels_use_shared_traffic_palette(self):
        """兩個診斷面板的紅綠灰必須就是 `shared.colors` 的常數（不是各自 inline）。"""
        from shared.colors import (
            TRAFFIC_GREEN, TRAFFIC_NEUTRAL, TRAFFIC_RED, TRAFFIC_YELLOW,
        )
        from src.ui.pages import data_registry_panel as drp
        from src.ui.pages import reconcile_panel as rp

        assert (rp._C_GREEN, rp._C_RED, rp._C_IDLE) == \
               (TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_NEUTRAL)
        assert (drp._C_GREEN, drp._C_YELLOW, drp._C_RED, drp._C_IDLE) == \
               (TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED, TRAFFIC_NEUTRAL)

    def test_same_emoji_same_color_across_panels(self):
        """同一個 🟡 / 🔴 在兩個面板必須是同一個 hex。"""
        from src.ui.pages import data_registry_panel as drp
        from src.ui.pages import reconcile_panel as rp

        assert rp._C_RED == drp._C_RED
        assert rp._C_GREEN == drp._C_GREEN
        assert rp._C_IDLE == drp._C_IDLE

    def test_registry_panel_missing_tag_uses_palette(self):
        """「缺」徽章的紅色也走同一份色票（原本是 inline `#f85149`）。"""
        from shared.colors import TRAFFIC_RED
        from src.ui.pages.data_registry_panel import compute_registry_groups

        _groups = compute_registry_groups({'data_registry': {
            'X': {'category': '🌐 國際金融', 'last_updated': 'N/A',
                  'rows': 0, 'frequency': 'daily', 'missing': True},
        }})
        _entry = next(iter(_groups.values()))[0]
        assert _entry['color'] == TRAFFIC_RED
        assert _entry['emoji'] == '🔴'


# ══════════════════════════════════════════════════════════════════
# E. 校準面板：顯示「實際生效」的門檻，不是 json 檔面值
# ══════════════════════════════════════════════════════════════════

class TestCalibrationPanel:

    @contextlib.contextmanager
    def _patched_json(self, tmp_path, payload: str):
        """把 `shared.macro_calibration._CALIBRATION_PATH` 指到暫存檔。

        `calibration_ui._show_threshold_status` 與 `load_calibrated_thresholds`
        都讀同一個模組屬性，patch 一次兩邊都吃到（這正是它們該同源的證明）。
        """
        import shared.macro_calibration as mc
        _f = tmp_path / 'macro_thresholds.json'
        _f.write_text(payload, encoding='utf-8')
        _old = mc._CALIBRATION_PATH
        mc._CALIBRATION_PATH = str(_f)
        try:
            yield
        finally:
            mc._CALIBRATION_PATH = _old

    @contextlib.contextmanager
    def _capture_st(self):
        """收 `st.caption` / `st.warning` 的輸出。"""
        from src.ui.pages import calibration_ui as cu
        _caps: list[str] = []
        _warns: list[str] = []
        _old_c, _old_w = cu.st.caption, cu.st.warning
        cu.st.caption = lambda body='', *a, **k: _caps.append(str(body))
        cu.st.warning = lambda body='', *a, **k: _warns.append(str(body))
        try:
            yield _caps, _warns
        finally:
            cu.st.caption, cu.st.warning = _old_c, _old_w

    def test_shows_effective_thresholds_for_valid_json(self, tmp_path):
        from shared.macro_calibration import load_calibrated_thresholds
        from src.ui.pages.calibration_ui import _show_threshold_status

        with self._patched_json(tmp_path,
                                '{"HEALTH_DEFENSE_THRESHOLD": 40, "BULL_MIN_SCORE": 3}'):
            _h, _s = load_calibrated_thresholds()
            with self._capture_st() as (_caps, _warns):
                _show_threshold_status()
        assert (_h, _s) == (40, 3), '前提：合法值應被 loader 採用'
        assert _caps, '「現行門檻」caption 從來沒被渲染 —— 這正是 B6-a 修過的 path bug'
        assert f'<{_h}' in _caps[0] and f'≥{_s}' in _caps[0], _caps
        assert not _warns, f'合法設定不該出警告：{_warns}'

    def test_out_of_range_json_does_not_lie_about_effective_value(self, tmp_path):
        """json 寫 99（越界）→ loader 退回預設 35；面板必須印 35 並大聲說明。

        舊碼直接印 json 面值 99，但系統其實在用 35 —— 面板宣稱的門檻不是生效門檻。
        """
        from shared.macro_calibration import (
            HEALTH_DEFENSE_THRESHOLD_DEFAULT, load_calibrated_thresholds,
        )
        from src.ui.pages.calibration_ui import _show_threshold_status

        with self._patched_json(tmp_path,
                                '{"HEALTH_DEFENSE_THRESHOLD": 99, "BULL_MIN_SCORE": 4}'):
            _h, _s = load_calibrated_thresholds()
            with self._capture_st() as (_caps, _warns):
                _show_threshold_status()
        assert _h == HEALTH_DEFENSE_THRESHOLD_DEFAULT, '前提：99 越界應被打回預設'
        assert f'<{_h}' in _caps[0], f'caption 應印生效值 {_h}：{_caps}'
        assert '99' not in _caps[0], f'caption 不得印未生效的 json 面值 99：{_caps}'
        assert _warns and '99' in _warns[0], (
            f'json 與生效值不一致時必須出警告（§1 降級不靜默）：{_warns}')

    def test_missing_file_is_reported_not_silent(self, tmp_path):
        """檔案不存在 → 誠實說「尚未產生」，不是靜默 return（B6-a 修過的原 bug）。"""
        import shared.macro_calibration as mc
        from src.ui.pages.calibration_ui import _show_threshold_status

        _old = mc._CALIBRATION_PATH
        mc._CALIBRATION_PATH = str(tmp_path / 'definitely-not-here.json')
        try:
            with self._capture_st() as (_caps, _warns):
                _show_threshold_status()
        finally:
            mc._CALIBRATION_PATH = _old
        assert _caps and '尚未產生' in _caps[0], _caps
