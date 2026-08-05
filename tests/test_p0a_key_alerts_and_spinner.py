# -*- coding: utf-8 -*-
"""v19.176 P0-A — ⚡ 今日關鍵「假綠燈」+ 載入文案說謊 兩案的回歸鎖(§1)。

背景(2026-08-05 線上實機)
========================
1. **假綠燈**:首輪載入時頁首印「✅ 今日關鍵：門檻＋急變雙層掃描無異常」,
   但同一頁下方「🔍 總經警示詳情（🟡×2 🟢×3）」同時列著 CPI YoY 2.81%
   與美債 10Y 4.63% 兩筆黃燈。根因 = 頁首讀 `session_state['macro_alerts']`
   時該 key 尚未被頁面下方的 `section_mid.py:61-62` 寫入 → 讀到 `None`,
   而 `None` 被當成「掃過了、沒事」渲染成綠色斷言。
   → §1「Fail Loud, Never Fake」:**未評估 ≠ 無異常**。
2. **文案說謊**:spinner 宣告「約 30~60 秒」、按鈕 help 宣告「約 30~50 秒」,
   但 code 自己允許的最長等待 = `fetch_macro_bundle` 的
   `_AS_COMPLETED_TIMEOUT`(100s)+ `run_macro_trio_and_persist` 的
   `global_timeout_s`(200s)= 300s。實測冷載 72.4 秒正好落在使用者會
   誤判當機的區間。
   → 本檔把「文案宣稱的上界必須 ≥ code 逾時上限」機器化,下次改 timeout
     忘了改文案時 CI 直接擋下。

三個最容易出錯的輸入(§6)
=======================
1. `macro_alerts is None`(section_mid 這輪還沒跑)→ 必須中性灰,**不得**綠。
2. `macro_alerts == []`(跑了但 check_macro_alerts 一個指標都沒取到,
   macro_alert.py:143 `if raw is None: continue`)→ 同樣是「沒有結論」,
   也**不得**綠。
3. 門檻層未評估但急變層有料(VIX 急升)→ 要顯示該項,**且**必須揭露
   「本列僅含急變層」,不可讓使用者以為這就是今天的全部。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding='utf-8')


def _mk_threshold(level='yellow', key='cpi', label='CPI YoY（美）', value=2.81):
    """仿 check_macro_alerts 輸出的一筆 alert(欄位對齊 macro_alert.py:151-159)。"""
    return {'key': key, 'label': label, 'unit': '%', 'value': value,
            'level': level,
            'emoji': {'red': '🔴', 'yellow': '🟡', 'green': '🟢'}[level],
            'message': f'{label} 進入觀察區'}


# ═════════════════════════════════════════════════════════════════
# 修正一 · L2：collect_key_alerts 三態都會壓成 items == []
#   (故意記錄此事實 —— 這正是「綠燈判定不可以放在 L2」的理由)
# ═════════════════════════════════════════════════════════════════
class TestL2CannotDistinguishNotEvaluated:
    def test_none_and_empty_and_all_green_all_collapse_to_empty_items(self):
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        _none = collect_key_alerts(None, None)
        _empty = collect_key_alerts([], None)
        _all_green = collect_key_alerts([_mk_threshold('green')], None)
        assert _none['items'] == [] and _empty['items'] == []
        assert _all_green['items'] == [], 'green 不進橫幅(既有設計)'
        # 三種語意完全不同的輸入 → L2 回傳一模一樣。因此「能不能顯示綠燈」
        # 只能由 caller 另外把「有沒有真的評估過」傳給 render 層。
        assert _none == _empty == _all_green

    def test_l2_return_contract_unchanged(self):
        """P0-A 刻意不動 L2 回傳欄位(既有 caller / 回歸測試不被靜默改語意)。"""
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        assert collect_key_alerts(None, None) == {
            'items': [], 'n_red': 0, 'n_yellow': 0}


# ═════════════════════════════════════════════════════════════════
# 修正一 · L4：key_alerts_banner 必須把 None/[] 與「真的無異常」分開
# ═════════════════════════════════════════════════════════════════
class TestBannerNeverFakesGreen:
    _EMPTY = {'items': [], 'n_red': 0, 'n_yellow': 0}

    def test_not_scanned_must_not_render_green_all_clear(self):
        from shared.colors import TRAFFIC_GREEN
        from src.ui.render.macro_ui_components import key_alerts_banner
        html = key_alerts_banner(self._EMPTY, threshold_scanned=False)
        assert '無異常' not in html or '未評估 ≠ 無異常' in html, \
            '未評估時不得出現「無異常」結論(除非是在否定它)'
        assert '✅' not in html, '未評估不得用 ✅ 打勾'
        assert TRAFFIC_GREEN not in html, '§1:未評估絕不可進綠色分支'

    def test_not_scanned_renders_neutral_and_says_why(self):
        from shared.colors import TRAFFIC_NEUTRAL
        from src.ui.render.macro_ui_components import key_alerts_banner
        html = key_alerts_banner(self._EMPTY, threshold_scanned=False)
        assert TRAFFIC_NEUTRAL in html, '應使用 shared.colors 中性灰 SSOT'
        assert '尚未完成' in html
        assert '未評估 ≠ 無異常' in html, '必須明說「未評估」不是「沒事」'

    def test_scanned_and_empty_is_the_only_green_path(self):
        from shared.colors import TRAFFIC_GREEN
        from src.ui.render.macro_ui_components import key_alerts_banner
        html = key_alerts_banner(self._EMPTY, threshold_scanned=True)
        assert TRAFFIC_GREEN in html and '無異常' in html

    def test_default_arg_preserves_legacy_caller_semantics(self):
        """既有 caller / test 不傳旗標時行為不變(綠燈),避免靜默改語意。"""
        from src.ui.render.macro_ui_components import key_alerts_banner
        assert key_alerts_banner(self._EMPTY) == \
            key_alerts_banner(self._EMPTY, threshold_scanned=True)

    def test_delta_only_items_disclose_threshold_layer_pending(self):
        """門檻層沒評估、但急變層有料 → 顯示該項 + 揭露「僅含急變層」。"""
        from shared.signal_thresholds import KEY_ALERT_VIX_DAY_SPIKE_PCT
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        from src.ui.render.macro_ui_components import key_alerts_banner
        _mult = 1 + (KEY_ALERT_VIX_DAY_SPIKE_PCT + 5) / 100
        out = collect_key_alerts(None, {'vix': {'values': [15.0, 15.0 * _mult]}})
        assert len(out['items']) == 1
        html = key_alerts_banner(out, threshold_scanned=False)
        assert 'VIX 單日急升' in html
        assert '僅含急變層' in html, '不可讓使用者以為這 1 項就是今天的全部'

    def test_scanned_items_have_no_pending_note(self):
        from src.compute.macro.daily_key_alerts import collect_key_alerts
        from src.ui.render.macro_ui_components import key_alerts_banner
        out = collect_key_alerts([_mk_threshold('yellow')], {})
        html = key_alerts_banner(out, threshold_scanned=True)
        assert '僅含急變層' not in html


# ═════════════════════════════════════════════════════════════════
# 修正一 · L5：tab_macro 必須用 placeholder 延後填充(v19.171 同款手法)
# ═════════════════════════════════════════════════════════════════
class TestTabMacroDeferredFill:
    def test_uses_empty_placeholder_not_direct_markdown(self):
        text = _src('src/ui/tabs/tab_macro.py')
        assert '_key_alerts_slot = st.empty()' in text, \
            '頁首應只佔位(照 app.py:502 _gl_slot 手法),不可當場渲染'
        assert '_key_alerts_slot.markdown(' in text

    def test_placeholder_created_before_traffic_light_module(self):
        """版面位置不變:佔位仍在【模組一】紅綠燈之前(頁首)。"""
        text = _src('src/ui/tabs/tab_macro.py')
        assert (text.index('_key_alerts_slot = st.empty()')
                < text.index('【模組一】紅綠燈決策儀表板'))

    def test_fill_happens_after_section_mid_writes_macro_alerts(self):
        """關鍵:填充必須晚於 render_section_mid(它才是 macro_alerts 的寫入者)。"""
        text = _src('src/ui/tabs/tab_macro.py')
        _pos_mid = text.index('render_section_mid(_load_heavy')
        assert text.rindex('_fill_key_alerts()') > _pos_mid, \
            '填充點必須在 section_mid 之後,否則永遠讀到上一輪的值'

    def test_scanned_flag_is_actually_wired(self):
        text = _src('src/ui/tabs/tab_macro.py')
        assert 'threshold_scanned=bool(' in text, \
            'None/[] 三態判定必須真的接上 render 層,不能只改 L4 沒接線'

    def test_section_mid_is_still_the_only_writer(self):
        """假設檢查:若未來多了第二個 macro_alerts 寫入點,填充時機需重新檢視。

        「填充放在 render_section_mid 之後」的正確性完全建立在
        「section_mid 是唯一寫入者」上 —— 全 src/ 掃描把這個前提釘住。
        """
        _w_re = re.compile(r"session_state\[['\"]macro_alerts['\"]\]\s*=")
        _writers = sorted(
            p.relative_to(REPO).as_posix()
            for p in (REPO / 'src').rglob('*.py')
            if _w_re.search(p.read_text(encoding='utf-8'))
        )
        assert _writers == ['src/ui/tabs/macro/section_mid.py'], \
            f'macro_alerts 寫入點變了({_writers}),請重新確認填充時機'

    def test_session_reset_does_not_pop_macro_alerts(self):
        """v19.171 踩過的坑:on_click callback pop 掉 key → 填充讀到空。"""
        text = _src('src/ui/tabs/macro/handlers.py')
        _m = re.search(r"def _macro_session_reset\(\):(.*?)\ndef ", text, re.S)
        assert _m, '_macro_session_reset 不見了,請重新確認填充時機安全性'
        assert 'macro_alerts' not in _m.group(1), \
            'macro_alerts 被 on_click pop → 填充會讀到空,需改用其他傳遞方式'


# ═════════════════════════════════════════════════════════════════
# 修正二：載入文案宣稱的秒數上界 ≥ code 自己的逾時上限
# ═════════════════════════════════════════════════════════════════
def _macro_fetch_timeout_s() -> int:
    """從 macro_fetch_orchestrator 靜態解析 `_AS_COMPLETED_TIMEOUT`。

    該值是 function-local 變數(無法 import),故以 AST-lite 的 regex 解析:
    `max(_job_timeouts.values()) + <margin>`。
    """
    text = _src('src/services/macro_fetch_orchestrator.py')
    _blocks = re.findall(
        r"_job_timeouts(?:\s*=\s*|\.update\(\s*)\{(.*?)\}", text, re.S)
    assert _blocks, '找不到 _job_timeouts 定義 — 解析式已過時,請更新本測試'
    _vals = [int(v) for b in _blocks for v in re.findall(r":\s*(\d+)", b)]
    assert _vals, '_job_timeouts 解析不到數值'
    _m = re.search(
        r"_AS_COMPLETED_TIMEOUT\s*=\s*max\(_job_timeouts\.values\(\)\)\s*\+\s*(\d+)",
        text)
    assert _m, '_AS_COMPLETED_TIMEOUT 算式變了 — 請更新本測試'
    return max(_vals) + int(_m.group(1))


def _macro_trio_timeout_s() -> int:
    """從 macro_trio_orchestrator 解析 `global_timeout_s` 預設值。"""
    text = _src('src/services/macro_trio_orchestrator.py')
    _m = re.search(r"global_timeout_s\s*:\s*int\s*=\s*(\d+)", text)
    assert _m, 'global_timeout_s 簽名變了 — 請更新本測試'
    return int(_m.group(1))


def _tab_macro_spinner_text() -> str:
    text = _src('src/ui/tabs/tab_macro.py')
    _m = re.search(r"with st\.spinner\((.*?)\):", text, re.S)
    assert _m, '找不到 tab_macro 的 st.spinner 呼叫'
    return _m.group(1)


def test_call_site_uses_default_trio_timeout():
    """假設檢查:tab_macro 的呼叫沒有覆寫 global_timeout_s → 預設值即實際上限。"""
    text = _src('src/ui/tabs/tab_macro.py')
    _m = re.search(r"run_macro_trio_and_persist\(([^)]*)\)", text, re.S)
    assert _m, '找不到 run_macro_trio_and_persist 呼叫'
    assert 'global_timeout_s' not in _m.group(1), \
        'tab_macro 覆寫了 trio timeout → 本測試的上限來源需改讀該處'


def test_spinner_declared_upper_bound_covers_code_timeouts():
    """⛔ 本測試就是那個教訓的機器化版本(改 timeout 忘了改文案 → 這裡紅)。

    spinner 區塊內序列跑 fetch_macro_bundle 與 run_macro_trio_and_persist,
    兩段逾時可疊加 → 文案宣稱的「最長 N 秒」必須 ≥ 兩者之和。
    """
    _bound = _macro_fetch_timeout_s() + _macro_trio_timeout_s()
    _spinner = _tab_macro_spinner_text()
    _m = re.search(r'最長\s*(\d+)\s*秒', _spinner)
    assert _m, f'spinner 文案未宣告「最長 N 秒」上界:{_spinner!r}'
    _declared = int(_m.group(1))
    assert _declared >= _bound, (
        f'spinner 宣稱最長 {_declared} 秒,但 code 逾時上限是 {_bound} 秒'
        f'(fetch_macro_bundle {_macro_fetch_timeout_s()}s + '
        f'trio {_macro_trio_timeout_s()}s)—— 使用者會在第 {_declared + 1} 秒'
        f'誤判當機。請同步更新 tab_macro 三處文案。')


def test_every_declared_upper_bound_in_tab_macro_is_honest():
    """spinner 與兩顆按鈕 help 都宣告了上界 → 每一個都要 ≥ code 上限。"""
    _bound = _macro_fetch_timeout_s() + _macro_trio_timeout_s()
    _all = [int(n) for n in re.findall(r'最長\s*(\d+)\s*秒',
                                       _src('src/ui/tabs/tab_macro.py'))]
    assert len(_all) >= 3, f'預期 spinner + 2 顆按鈕 help 各宣告一次,實得 {_all}'
    assert all(n >= _bound for n in _all), \
        f'有文案宣稱的上界低於 code 上限 {_bound}s:{_all}'


def test_stale_lying_copy_removed():
    """釘死已知的三條說謊文案不得復活。"""
    text = _src('src/ui/tabs/tab_macro.py')
    assert '約 30~60 秒' not in text, 'spinner 舊假上界復活'
    assert '冷啟動約 30~50 秒' not in text, '按鈕 help 舊假上界復活'
    assert '首次 ~30-60s' not in _src('src/ui/tabs/tab_stock_grp.py'), \
        '批次分析舊假區間復活(該迴圈逐檔序列且無全域逾時,秒數無法固定)'


def test_spinner_separates_warm_cache_from_cold_start():
    """暖快取數秒 vs 冷啟動數十秒,兩種體感差 10 倍 → 文案必須分開講。"""
    _spinner = _tab_macro_spinner_text()
    assert '暖快取' in _spinner and '冷啟動' in _spinner


def test_stock_grp_copy_describes_structure_not_fake_seconds():
    """逐檔序列 + 無全域逾時 → 給結構與進度條,不給必然說謊的固定秒數。"""
    text = _src('src/ui/tabs/tab_stock_grp.py')
    assert '逐檔序列' in text and '進度條' in text
