"""B6-a v19.181 — 說明書 / 教學文案 vs 實作 對帳守衛。

【這批守衛在防什麼】
使用者把「📚 教學」分頁當**學習材料**在讀。前幾輪修過三批說謊文案，但每次
都是針對特定回報點狀修。這次全面對帳後發現同一個病灶反覆出現：

    可被 code 證實或證偽的數字 / 清單 **被手打進教學段落** → 之後跟實作漂開。

具體案發（全部已修，本檔釘住不准復發）：
  1. 衰退機率公式手寫 `1/(1+exp(0.5 + 0.55×spread))`，實作係數是 −1.5 / −0.8；
     連它自己附的「−2% → 78%」照自己的式子算也只有 65%（自我矛盾）。
  2. PMI 多源手寫「賽跑 10 個源(…MacroMicro…FinMind…)」，實際 8 源，
     MacroMicro v19.113 拔除、FinMind v19.85 拔除 —— 同一頁另一處早已是新版。
  3. 「站上 20MA 家數比」= 系統從未計算的量（旌旗指數其實是上漲佔比 5 日均）。
  4. 教學卡宣稱 N 張、實際只渲染 N−2 張（兩個 EDU key 對不到 registry）。
  5. 文案叫使用者「前往『ETF回測』」—— 該分頁 v18.265 已刪。

【設計原則（吃過虧才寫下來的）】
- **優先行為斷言**：能呼叫 production 函式對答案的，就不要比字串。
  例：衰退機率直接呼叫 `macro_core.recession_probability()` 對帳，
  而不是去 grep 文案裡有沒有寫某個數字 —— 後者「照抄實作字面」，
  實作錯了守衛也跟著錯，永遠測不出問題。
- **來源斷言 > 數值斷言**：對「文案裡的數字」，斷言它**來自 SSOT**
  （AST 確認是 f-string 欄位 / 是 §§TOKEN§§），而不是斷言它等於某個常值。
  斷言等於常值 = 把同一個數字抄第三份，漂移時三份一起錯。
- **要掃原始碼就用 AST**：ast 天然看不到註解；docstring 另外顯式排除；
  失敗訊息一律印 `file:line` + 該行原文，避免無從查起的假紅燈。
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: `§§TOKEN§§` 佔位符樣式（與 `tab_edu._resolve_edu_tokens` 同一約定）
_TOKEN_RE = re.compile(r'§§[A-Z0-9_]+§§')


# ════════════════════════════════════════════════════════════════
# streamlit stub —— 與 tests/test_macro_classroom.py 同模式（進出各一次）
# ════════════════════════════════════════════════════════════════

class _MarkdownRecorder:
    """記下所有 st.markdown / st.caption 的第一個位置參數，供 render 後對帳。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, body='', *a, **k):
        self.calls.append(str(body))
        return None

    @property
    def text(self) -> str:
        return '\n'.join(self.calls)


def _install_stub(recorder: _MarkdownRecorder):
    _mod = types.ModuleType('streamlit')
    _mod._is_test_stub = True

    def _noop(*a, **k):
        return None

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    for _name in ('divider', 'info', 'success', 'warning', 'error',
                  'metric', 'code', 'plotly_chart', 'dataframe'):
        setattr(_mod, _name, _noop)
    _mod.markdown = recorder
    _mod.caption = recorder
    _mod.expander = lambda *a, **k: _Ctx()

    def _cache_data(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

    _mod.cache_data = _cache_data
    _mod.cache_resource = _cache_data
    _mod.columns = lambda spec, **k: [
        _Ctx() for _ in range(spec if isinstance(spec, int) else len(spec))
    ]
    _mod.session_state = {}
    _mod.secrets = {}
    sys.modules['streamlit'] = _mod


def _reload_targets():
    import importlib
    for _name in ('src.ui.tabs.tab_edu', 'src.ui.tabs.macro_classroom'):
        if _name in sys.modules:
            try:
                importlib.reload(sys.modules[_name])
            except Exception:
                pass


@pytest.fixture(scope='module')
def rendered_classroom():
    """在 stub 下真的跑一次 `render_principle_classroom()`，回傳渲染出的全文。

    這是**行為**斷言的基底：對帳的是「使用者真的會看到的字」，
    不是原始碼字面 —— 佔位符沒被替換、章節沒被渲染，這裡都會現形。
    """
    # ① 先在**真 streamlit** 下 import 目標。`src/ui/tabs/__init__.py` 是 eager
    #    barrel,會連鎖拉進 `src/ui/pages/` —— 若在 stub 視窗內首次 import,
    #    近千個模組的 module-level `st` 會永久綁在待丟棄的 stub 上。
    import src.ui.tabs.macro_classroom  # 只為觸發 import,不取用符號
    import src.ui.tabs.tab_edu  # noqa: F401 — 同上
    from tests.conftest import rebind_modules_bound_to

    _saved = sys.modules.get('streamlit')
    _rec = _MarkdownRecorder()
    _install_stub(_rec)
    _stub = sys.modules['streamlit']
    _reload_targets()
    try:
        from src.ui.tabs.tab_edu import render_principle_classroom
        render_principle_classroom()
        yield _rec.text
    finally:
        if _saved is not None:
            sys.modules['streamlit'] = _saved
        else:
            sys.modules.pop('streamlit', None)
        _reload_targets()
        # ② 補漏:針對性 reload 仍綁著 stub 的模組(渲染過程中的函式內 import)。
        rebind_modules_bound_to(_stub)


# ════════════════════════════════════════════════════════════════
# 1. 佔位符必須全部被 SSOT 值替換掉（漏一個 = 畫面上印出 §§XXX§§）
# ════════════════════════════════════════════════════════════════

class TestEduTokensAllResolve:

    def test_rendered_classroom_has_no_unresolved_token(self, rendered_classroom):
        _left = sorted(set(_TOKEN_RE.findall(rendered_classroom)))
        assert not _left, (
            f'原理教室渲染後仍有未替換的佔位符 {_left} —— '
            f'請到 `tab_edu._edu_tokens()` 補上對應的 SSOT 取值（拼錯字也會這樣）。'
        )

    def test_every_token_used_in_chapters_is_registered(self):
        """章節裡出現的每個 token 都要在 `_edu_tokens()` 有登記。

        與上一條互補而非重複：這條在**不渲染**的情況下比對集合，
        能指出是「哪個章節」用了沒登記的 token（上一條只知道有漏）。
        """
        from src.ui.tabs.tab_edu import _PRINCIPLE_CHAPTERS, _edu_tokens
        _registered = set(_edu_tokens().keys())
        for _i, (_title, _body) in enumerate(_PRINCIPLE_CHAPTERS, 1):
            for _tok in set(_TOKEN_RE.findall(_title + _body)):
                assert _tok in _registered, (
                    f'第 {_i} 章「{_title[:24]}」用了未登記的佔位符 {_tok}；'
                    f'已登記的有：{sorted(_registered)}'
                )

    def test_no_token_resolves_to_empty_string(self):
        from src.ui.tabs.tab_edu import _edu_tokens
        for _k, _v in _edu_tokens().items():
            assert str(_v).strip(), f'{_k} 解析成空字串 —— 畫面會出現空白數字'

    def test_every_token_in_source_is_registered(self):
        """涵蓋 `_PRINCIPLE_CHAPTERS` 以外的段落（例：策略3 資金動能 expander）。

        那些 expander 不在 `render_principle_classroom()` 裡，上面兩條測不到；
        這條直接掃 tab_edu 原始碼的**字串常值**（AST，排除 docstring），
        確保每個佔位符都有登記 —— 沒登記就會原樣印在畫面上。
        """
        from src.ui.tabs.tab_edu import _edu_tokens
        _registered = set(_edu_tokens().keys())
        _path = _ROOT / 'src/ui/tabs/tab_edu.py'
        _text = _path.read_text(encoding='utf-8')
        _lines = _text.splitlines()
        _tree = ast.parse(_text)
        _skip = _docstring_nodes(_tree)
        _bad: list[str] = []
        for _n in ast.walk(_tree):
            if not (isinstance(_n, ast.Constant) and isinstance(_n.value, str)):
                continue
            if id(_n) in _skip:
                continue
            for _tok in set(_TOKEN_RE.findall(_n.value)):
                # `_edu_tokens()` 自己的 key 定義也是字串常值，會命中；那是登記本身
                if _tok in _registered:
                    continue
                _ln = getattr(_n, 'lineno', 0)
                _raw = _lines[_ln - 1].strip() if 0 < _ln <= len(_lines) else ''
                _bad.append(f'  {_path}:{_ln}  未登記 {_tok}\n      → {_raw}')
        assert not _bad, (
            '教學文案用了未登記的佔位符（會原樣印在畫面上）：\n'
            + '\n'.join(_bad)
            + f'\n已登記：{sorted(_registered)}'
        )

    def test_liquidity_section_is_token_resolved(self):
        """來源斷言：資金動能 expander 的 markdown 必須經過 `_resolve_edu_tokens`。

        該段用了 §§BREADTH_*§§ / §§FUT_*§§，若有人把 `_resolve_edu_tokens(...)`
        拿掉，畫面就會直接印出 `§§BREADTH_BULL§§`。AST 確認呼叫存在。
        """
        _tree = ast.parse((_ROOT / 'src/ui/tabs/tab_edu.py').read_text(encoding='utf-8'))
        _wrapped = False
        for _n in ast.walk(_tree):
            if not (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Name)
                    and _n.func.id == '_resolve_edu_tokens'):
                continue
            for _arg in _n.args:
                if (isinstance(_arg, ast.Constant) and isinstance(_arg.value, str)
                        and '§§BREADTH_BULL§§' in _arg.value):
                    _wrapped = True
        assert _wrapped, (
            '資金動能（策略3 章節 3/3）那段 markdown 沒有被 `_resolve_edu_tokens(...)` 包住 —— '
            '畫面會直接印出 §§BREADTH_BULL§§ 之類的原始佔位符。'
        )


# ════════════════════════════════════════════════════════════════
# 2. 衰退機率：文案數字必須等於 production 函式算出來的值
#    （行為斷言 —— 直接呼叫 macro_core，不比字串）
# ════════════════════════════════════════════════════════════════

class TestRecessionProbabilityParity:

    @pytest.mark.parametrize('spread, token', [
        (0.0,  '§§RECESSION_P_AT_0§§'),
        (-1.0, '§§RECESSION_P_AT_M1§§'),
        (-2.0, '§§RECESSION_P_AT_M2§§'),
    ])
    def test_doc_number_matches_production_function(self, spread, token):
        from src.data.macro.macro_core import recession_probability
        from src.ui.tabs.tab_edu import _edu_tokens

        _truth = recession_probability(spread)
        assert _truth is not None
        _doc = float(_edu_tokens()[token])
        # 文案取整數位顯示，容差 0.5 個百分點
        assert abs(_doc - _truth) <= 0.5, (
            f'說明書寫 spread={spread}% → {_doc}%，'
            f'但 `macro_core.recession_probability({spread})` 回 {_truth}%。'
            f'兩邊已漂移 —— 以 code 為準改文案（文案數字應由 '
            f'`shared/signal_thresholds.RECESSION_LOGIT_COEF_*` 產生）。'
        )

    def test_doc_coefficients_are_the_ssot_ones(self):
        from shared.signal_thresholds import (
            RECESSION_LOGIT_COEF_INTERCEPT,
            RECESSION_LOGIT_COEF_SPREAD,
        )
        from src.ui.tabs.tab_edu import _edu_tokens
        _t = _edu_tokens()
        assert float(_t['§§RECESSION_COEF_SPREAD§§']) == RECESSION_LOGIT_COEF_SPREAD
        assert float(_t['§§RECESSION_COEF_INTERCEPT§§']) == RECESSION_LOGIT_COEF_INTERCEPT

    def test_old_wrong_formula_not_resurrected(self, rendered_classroom):
        """舊版手寫係數 `0.5 + 0.55 × spread` 不可復活。

        只釘那組**具體錯值**的組合，不釘「不准出現 0.55」——
        後者會在別的章節誤傷（0.55 在統計段落是合法數字）。
        """
        assert '0.55 ×' not in rendered_classroom, (
            '衰退機率段又出現手寫係數 0.55 —— 實作用的是 '
            'RECESSION_LOGIT_COEF_SPREAD/_INTERCEPT，請走 §§TOKEN§§。'
        )

    def test_probability_is_monotone_decreasing_in_spread(self):
        """概念正確性：利差越負 → 衰退機率越高。文案舉的三個值必須符合這個方向。

        這條抓的是「數字換過但方向講反」——比對值更難造假。
        """
        from src.ui.tabs.tab_edu import _edu_tokens
        _t = _edu_tokens()
        _p0 = float(_t['§§RECESSION_P_AT_0§§'])
        _pm1 = float(_t['§§RECESSION_P_AT_M1§§'])
        _pm2 = float(_t['§§RECESSION_P_AT_M2§§'])
        assert _p0 < _pm1 < _pm2, (
            f'倒掛越深機率應越高，實際 0%→{_p0} / −1%→{_pm1} / −2%→{_pm2}'
        )


# ════════════════════════════════════════════════════════════════
# 3. PMI 多源：文案的來源清單必須「產自」registry，而不是手抄
# ════════════════════════════════════════════════════════════════

def _pmi_chapter() -> tuple[str, str]:
    from src.ui.tabs.tab_edu import _PRINCIPLE_CHAPTERS
    for _title, _body in _PRINCIPLE_CHAPTERS:
        if 'PMI' in _title:
            return _title, _body
    pytest.fail('找不到 PMI 章節（章節標題可能被改過）')


class TestPmiSourceListParity:

    def test_chapter_derives_source_list_from_registry(self):
        """來源斷言：章節原文必須用佔位符，不得手打來源鏈 / 來源數。

        這比「斷言文字等於某個清單」有價值 —— 後者只是把清單抄第三份。
        """
        _title, _body = _pmi_chapter()
        assert '§§PMI_SOURCES§§' in _body, (
            'PMI 章的來源鏈又被手打了；請寫 §§PMI_SOURCES§§ 讓它由 '
            '`macro_core.PMI_SOURCE_REGISTRY` 產生。'
        )
        assert '§§PMI_SOURCE_COUNT§§' in _body, (
            'PMI 章的「N 個源」又被手打了；請寫 §§PMI_SOURCE_COUNT§§。'
        )

    def test_rendered_list_equals_registry_order(self, rendered_classroom):
        from src.data.macro.macro_core import PMI_SOURCE_REGISTRY
        _names = [_n for _n, _fn in PMI_SOURCE_REGISTRY]
        _chain = ' → '.join(_names)
        assert _chain in rendered_classroom, (
            f'渲染出的 PMI 來源鏈與 registry 不符。registry 順序為：{_chain}'
        )
        assert f'{len(_names)} 個源' in rendered_classroom, (
            f'渲染出的來源數與 registry 不符（registry 有 {len(_names)} 個）'
        )

    def test_retired_sources_not_mentioned_as_tw_pmi_source(self, rendered_classroom):
        """已拔除的來源不可再以「本系統的 TW PMI 來源」身分出現。

        v19.85 拔 FinMind（`TaiwanEconomicIndicator` 這個 dataset 根本不存在）、
        v19.113 拔 MacroMicro（美國 IP + NAS proxy 實測 host 級攔截）。
        注意：只檢查 PMI 章，**不檢查全站** —— MacroMicro 在「美國 PMI」的
        fallback 鏈裡仍是合法來源（CLAUDE.md §2.1），全站禁字會誤傷。
        """
        from src.data.macro.macro_core import PMI_SOURCE_REGISTRY
        _names = {_n for _n, _fn in PMI_SOURCE_REGISTRY}
        for _dead in ('MacroMicro', 'FinMind'):
            assert _dead not in _names, (
                f'{_dead} 又回到 PMI_SOURCE_REGISTRY —— 若是刻意加回，'
                f'請同步更新本測試與 CLAUDE.md §2.1。'
            )
        _title, _body = _pmi_chapter()
        for _dead in ('MacroMicro', 'FinMind'):
            assert _dead not in _body, (
                f'PMI 章又把 {_dead} 寫成 TW PMI 來源（該源已拔除）。'
            )

    def test_no_average_claim(self, rendered_classroom):
        """CLAUDE.md §2.1：PMI 多源**禁止平均**，取第一個命中。"""
        assert '禁止平均' in rendered_classroom, (
            'PMI 章遺失「禁止平均」的說明 —— 這是 §2.1 的硬規則，'
            '讀者若以為系統會平均多源，會對數字的來源產生錯誤認知。'
        )


# ════════════════════════════════════════════════════════════════
# 4. 旌旗指數：文案宣稱的公式，拿真資料餵進 production 函式驗
# ════════════════════════════════════════════════════════════════

class TestJingqiFormulaParity:

    def test_jingqi_is_ad_ratio_5day_mean(self):
        """行為斷言：`compute_and_store_jingqi` 真的算「上漲佔比的 5 日均」。

        這條釘的是文案（教學頁 + 名詞表 + KPI 卡）共同宣稱的那句話。
        若哪天實作改成別的（例如真的改抓站上均線家數比），這裡先紅。
        """
        import importlib

        # 先在真 streamlit 下 import,stub 視窗內才不會有「首次 import」
        import src.services.jingqi_calc  # noqa: F401 — 只為觸發 import,不取用符號
        from tests.conftest import rebind_modules_bound_to

        pd = pytest.importorskip('pandas')
        _saved = sys.modules.get('streamlit')
        _install_stub(_MarkdownRecorder())
        _stub = sys.modules['streamlit']
        try:
            import src.services.jingqi_calc as _jq
            importlib.reload(_jq)
            # 6 筆，只有最後 5 筆該被採用 → 平均 = (20+30+40+50+60)/5 = 40
            _df = pd.DataFrame({'ad_ratio': [99.0, 20.0, 30.0, 40.0, 50.0, 60.0]})
            _jq.compute_and_store_jingqi(_df)
            _info = sys.modules['streamlit'].session_state['jingqi_info']
            assert _info['source'] == 'ADL'
            assert _info['avg'] == pytest.approx(40.0), (
                f"旌旗應為 ad_ratio 最後 5 筆的平均 (=40.0)，實際 {_info['avg']}；"
                f'若實作已改公式，教學頁 / 名詞表 / KPI 卡三處說明都要同步改。'
            )
        finally:
            if _saved is not None:
                sys.modules['streamlit'] = _saved
            else:
                sys.modules.pop('streamlit', None)
            importlib.reload(sys.modules['src.services.jingqi_calc'])
            rebind_modules_bound_to(_stub)

    def test_term_table_states_the_real_formula(self):
        from src.ui.render.ui_widgets import BREADTH_JINGQI
        assert 'ad_ratio' in BREADTH_JINGQI.formula
        assert '5' in BREADTH_JINGQI.formula

    def test_fabricated_name_stays_blacklisted(self):
        """「站上均線家數比」是系統從未計算的量，必須留在退役名單裡。"""
        from src.ui.render.ui_widgets import BREADTH_DEPRECATED_TITLES
        for _dead in ('站上均線家數比', '站上 20MA 家數比'):
            assert _dead in BREADTH_DEPRECATED_TITLES, (
                f'「{_dead}」被移出退役名單 —— 這是 §1 反捏造釘死的假描述，不可復活。'
            )

    def test_breadth_bands_in_doc_come_from_ssot(self):
        from shared.signal_thresholds import BREADTH_BULL_PCT, BREADTH_NEUTRAL_PCT
        from src.ui.tabs.tab_edu import _edu_tokens
        _t = _edu_tokens()
        assert float(_t['§§BREADTH_BULL§§']) == BREADTH_BULL_PCT
        assert float(_t['§§BREADTH_NEUTRAL§§']) == BREADTH_NEUTRAL_PCT


# ════════════════════════════════════════════════════════════════
# 5. 外資期貨 / 融資 / 韭菜：三組門檻的文案值 == SSOT 值
# ════════════════════════════════════════════════════════════════

class TestThresholdTokensMatchSsot:

    def test_foreign_futures_tokens(self):
        from shared.signal_thresholds import (
            FOREIGN_5D_NET_THRESHOLD_YI,
            FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD,
            FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS,
            FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS,
        )
        from src.ui.tabs.tab_edu import _edu_tokens
        _t = _edu_tokens()

        def _num(tok):
            return float(_t[tok].replace(',', ''))

        assert _num('§§FUT_DEFENSE_LOTS§§') == FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD
        assert _num('§§FUT_V4_RED_LOTS§§') == FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS
        assert _num('§§FUT_V4_YELLOW_LOTS§§') == FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS
        assert _num('§§FOREIGN_5D_YI§§') == FOREIGN_5D_NET_THRESHOLD_YI

    def test_three_futures_thresholds_stay_distinct(self):
        """§4.1 防呆：三個門檻語意不同、刻意不統一。

        若哪天有人「順手合併」成同一個數字，教學頁那段「為什麼有三個門檻」
        就會變成假說明 —— 這裡先紅，提醒同步改文案（或別合併）。
        """
        from shared.signal_thresholds import (
            FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD,
            FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS,
            FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS,
        )
        _vals = {
            abs(FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD),
            abs(FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS),
            abs(FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS),
        }
        assert len(_vals) == 3, (
            f'三個外資期貨門檻出現重複值 {_vals}；教學頁「為何有三個不同門檻」'
            f'那段說明需同步調整。'
        )

    def test_margin_tokens(self):
        from shared.signal_thresholds import (
            MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
            MARGIN_BALANCE_WARN_THRESHOLD_YI,
        )
        from src.ui.tabs.tab_edu import _edu_tokens
        _t = _edu_tokens()
        assert float(_t['§§MARGIN_WARN_YI§§'].replace(',', '')) == \
            MARGIN_BALANCE_WARN_THRESHOLD_YI
        assert float(_t['§§MARGIN_OVERHEAT_YI§§'].replace(',', '')) == \
            MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI

    def test_margin_warn_is_below_overheat(self):
        """黃線必須低於紅線 —— 教學頁把 2500 講成「過熱」曾是實際 bug。"""
        from shared.signal_thresholds import (
            MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
            MARGIN_BALANCE_WARN_THRESHOLD_YI,
        )
        assert MARGIN_BALANCE_WARN_THRESHOLD_YI < MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI

    def test_leek_tokens_use_futures_scale_not_0_100_scale(self):
        """§4.1 量綱：畫面「韭菜指數」是 ±% 的法人空多比，不是 0~100 指數。

        釘住教學頁引用的是 `LEEK_ALERT_*`（±%），而不是 `LEEK_*_THRESHOLD`
        （0~100，全 repo 0 consumer）—— 兩者混用正是舊版本章的錯。
        """
        from src.config import LEEK_ALERT_HIGH_PCT, LEEK_ALERT_LOW_PCT
        from src.ui.tabs.tab_edu import _edu_tokens
        _t = _edu_tokens()
        assert float(_t['§§LEEK_ALERT_HIGH§§']) == LEEK_ALERT_HIGH_PCT
        assert float(_t['§§LEEK_ALERT_LOW§§']) == LEEK_ALERT_LOW_PCT
        assert LEEK_ALERT_LOW_PCT < 0 < LEEK_ALERT_HIGH_PCT, (
            '法人空多比門檻應為一正一負（值域約 ±100，中位 0）；'
            '若變成兩個正數，代表誤用了 0~100 那組門檻。'
        )

    def test_leek_chapter_discloses_the_two_meanings(self, rendered_classroom):
        """概念正確性：同名不同義必須在同一段講清楚，否則讀者必然誤判。"""
        assert '法人空多比' in rendered_classroom, (
            '散戶情緒章沒有點出畫面上那個「韭菜指數」的真身（小台法人空多比），'
            '讀者會拿 0~100 的門檻去看 ±% 的數字。'
        )


# ════════════════════════════════════════════════════════════════
# 6. 教學卡張數：宣稱的數量 == 真的渲染得出來的數量
# ════════════════════════════════════════════════════════════════

class TestEduCardCountHonesty:

    #: 已知「寫了但掛不上 registry identifier」的 EDU key（= 永遠不會顯示）
    #: 'NAPM'        → registry 的台灣 PMI 那筆 identifier 是 'cier-pmi'
    #: 'NDC_signal'  → registry 用 'TaiwanBusinessIndicator' / 'NDC_signal_v2(_fallback)'
    KNOWN_ORPHAN_EDU_KEYS = frozenset({'NAPM', 'NDC_signal'})

    def test_orphan_edu_keys_are_the_known_set(self):
        """EDU 文稿掛不上 registry identifier → 永遠不會顯示在教學頁。

        新增孤兒時本測試會紅，屆時請二選一：
          (a) 把 EDU key 改成 registry 真正在用的 identifier（首選），或
          (b) 確認是刻意的，把 key 加進 `KNOWN_ORPHAN_EDU_KEYS`
              —— 教學頁會自動把張數差揭露給使用者，不必改文案。
        """
        from src.data.core.data_registry import DATA_REGISTRY, EDU_GUIDE
        _ids = {_e.get('identifier') for _e in DATA_REGISTRY}
        _orphans = {_k for _k in EDU_GUIDE if _k not in _ids}
        assert _orphans == set(self.KNOWN_ORPHAN_EDU_KEYS), (
            f'孤兒 EDU key 集合變了：實際 {sorted(_orphans)}，'
            f'預期 {sorted(self.KNOWN_ORPHAN_EDU_KEYS)}。'
            f'（EDU_GUIDE 共 {len(EDU_GUIDE)} 篇）'
        )

    def test_page_claim_equals_rendered_card_count(self):
        """行為斷言：教學頁報的張數 == 迴圈真的會渲染的張數。

        重算一次頁面的渲染清單（與 `tab_edu` 同一組 registry API），
        確認它等於「EDU 篇數 − 孤兒數」——「說的」與「畫的」對得上。
        """
        from src.data.core import get_by_category, get_categories, get_edu
        from src.data.core.data_registry import EDU_GUIDE
        _renderable = sum(
            1
            for _cat in get_categories()
            for _e in get_by_category(_cat)
            if get_edu(_e.get('identifier')) is not None
        )
        assert _renderable == len(EDU_GUIDE) - len(self.KNOWN_ORPHAN_EDU_KEYS), (
            f'渲染得出來的教學卡 {_renderable} 張，'
            f'但 EDU_GUIDE {len(EDU_GUIDE)} 篇 − 孤兒 '
            f'{len(self.KNOWN_ORPHAN_EDU_KEYS)} 篇 對不上 —— '
            f'很可能有 identifier 在 DATA_REGISTRY 重複登記，導致同一張卡印兩次。'
        )

    def test_page_reports_renderable_count_not_written_count(self):
        """來源斷言：頁面報數必須數「渲染清單」，不可直接印 get_edu_count()。"""
        _src = (_ROOT / 'src/ui/tabs/tab_edu.py').read_text(encoding='utf-8')
        _tree = ast.parse(_src)
        _assigned: set[str] = set()
        for _n in ast.walk(_tree):
            # 兩種都要收：`x = ...`（Assign）與 `x: T = ...`（AnnAssign）
            if isinstance(_n, ast.Assign):
                _assigned |= {_t.id for _t in _n.targets if isinstance(_t, ast.Name)}
            elif isinstance(_n, ast.AnnAssign) and isinstance(_n.target, ast.Name):
                _assigned.add(_n.target.id)
        assert '_cat_pairs' in _assigned, (
            'tab_edu 不再先把「要渲染的卡片清單」算出來 —— '
            '報數會退回 len(EDU_GUIDE)，又變成宣稱多於實際。'
        )

    def test_tw_pmi_card_not_wired_to_us_fred_series(self):
        """§1 反捏造：台灣 PMI 的值不可配美國 NAPM 的歷史分布算 Z-Score。

        `macro_info['ism_pmi']` 的內容其實是**台灣** PMI
        （`macro_snapshot.fetch_tw_pmi_block` docstring 明講），
        若把 FRED `NAPM`（美國 ISM）序列掛上去，Z 與閾值線都是跨國混算的假值。
        """
        from shared.fred_series import FRED_NAPM
        from src.ui.tabs.tab_edu import _FRED_EDU_UNITS
        assert FRED_NAPM not in _FRED_EDU_UNITS, (
            f'`_FRED_EDU_UNITS` 又掛回 {FRED_NAPM}（美國 ISM 序列）。'
            f'該 key 對到的當期值是台灣 PMI，混算的 Z-Score 是假的。'
            f'要恢復趨勢圖請改接台灣 PMI 歷史序列（tw_macro.fetch_pmi_history）。'
        )


# ════════════════════════════════════════════════════════════════
# 7. VCP / 風控數字：AST 確認是「SSOT 代入」而非手打
# ════════════════════════════════════════════════════════════════

def _fstring_names(path: pathlib.Path) -> set[str]:
    """回傳檔案內所有 f-string 插值欄位用到的 Name（含 attribute 的根 Name）。"""
    _tree = ast.parse(path.read_text(encoding='utf-8'))
    _names: set[str] = set()
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.FormattedValue):
            for _sub in ast.walk(_n.value):
                if isinstance(_sub, ast.Name):
                    _names.add(_sub.id)
    return _names


class TestVcpRiskNumbersDeriveFromSsot:

    REQUIRED = (
        'RR_MIN',
        'RR_DEFAULT_TARGET_GAIN',
        'STOP_LOSS_DEFAULT_PCT',
        'ATR_STOP_MULTIPLIER',
        'VCP_ATR_CONTRACTION_RATIO',
    )

    def test_numbers_are_interpolated_from_constants(self):
        _used = _fstring_names(_ROOT / 'src/ui/tabs/tab_edu.py')
        _missing = [_c for _c in self.REQUIRED if _c not in _used]
        assert not _missing, (
            f'VCP / 風控章的這些數字沒有從 SSOT 代入：{_missing}。'
            f'手打數字會在常數調整時變成過期文案（§3.3）。'
        )

    def test_imported_values_equal_ssot(self):
        import shared.signal_thresholds as _st
        import src.ui.tabs.tab_edu as _edu
        for _c in self.REQUIRED:
            assert getattr(_edu, _c) == getattr(_st, _c), (
                f'tab_edu.{_c} 與 shared.signal_thresholds.{_c} 不一致'
            )

    def test_no_hand_written_rr_3_to_1_claim(self):
        """舊版寫「盈虧比 ≥ 3:1」，實際門檻是 RR_MIN(=2.0)。

        AST 掃字串常值（自動排除註解；docstring 另外排除），
        失敗時印出 file:line + 原文。
        """
        _bad = _scan_string_literals(
            _ROOT / 'src/ui/tabs/tab_edu.py', ('盈虧比 ≥ 3:1', '盈虧比 >= 3:1'))
        assert not _bad, _format_hits(_bad)


# ════════════════════════════════════════════════════════════════
# 8. 已刪功能：UI 字串不可再指路到不存在的分頁
#    （AST 掃 string literal，排除 docstring；註解本來就不在 AST 裡）
# ════════════════════════════════════════════════════════════════

def _docstring_nodes(tree: ast.AST) -> set[int]:
    """收集所有 docstring 的 Constant 節點 id，掃描時排除。"""
    _ids: set[int] = set()
    for _n in ast.walk(tree):
        if isinstance(_n, (ast.Module, ast.ClassDef,
                           ast.FunctionDef, ast.AsyncFunctionDef)):
            _body = getattr(_n, 'body', None)
            if (_body and isinstance(_body[0], ast.Expr)
                    and isinstance(_body[0].value, ast.Constant)
                    and isinstance(_body[0].value.value, str)):
                _ids.add(id(_body[0].value))
    return _ids


def _scan_string_literals(path: pathlib.Path,
                          needles: tuple[str, ...]) -> list[tuple[str, int, str, str]]:
    """回傳 [(file, lineno, needle, 該行原文)]；只看非 docstring 的 str 常值。"""
    _text = path.read_text(encoding='utf-8')
    _lines = _text.splitlines()
    try:
        _tree = ast.parse(_text)
    except SyntaxError as _e:
        pytest.fail(f'{path} 無法解析（語法錯誤）：{_e}')
    _skip = _docstring_nodes(_tree)
    _hits: list[tuple[str, int, str, str]] = []
    for _n in ast.walk(_tree):
        if not (isinstance(_n, ast.Constant) and isinstance(_n.value, str)):
            continue
        if id(_n) in _skip:
            continue
        for _needle in needles:
            if _needle in _n.value:
                _ln = getattr(_n, 'lineno', 0)
                _raw = _lines[_ln - 1].strip() if 0 < _ln <= len(_lines) else ''
                _hits.append((str(path), _ln, _needle, _raw))
    return _hits


def _format_hits(hits) -> str:
    return '偵測到過期文案：\n' + '\n'.join(
        f'  {_f}:{_ln}  含「{_nd}」\n      → {_raw}' for _f, _ln, _nd, _raw in hits
    )


#: needle → 為什麼禁（失敗訊息會一起印出來，避免下一個人不知道為何紅）
_DEAD_UI_REFERENCES: dict[str, str] = {
    'ETF回測': 'ETF 回測分頁已於 v18.265 隨 etf_tab_backtest.py 刪除',
    '🩺 體檢轉機': '體檢轉機獨立分頁已於 v19.164 退役真刪（併入 🏆 個股組合）',
    '🌐 總經 Tab': 'Tab 真名是「🌍 總經」（app.py:568）',
    '「🌐 總經」': 'Tab 真名是「🌍 總經」（app.py:568）',
    '📈 個股 Tab': 'Tab 真名是「🔬 個股」（app.py:584）',
    '「📈 個股」': 'Tab 真名是「🔬 個股」（app.py:584）',
}


class TestNoPointersToDeletedTabs:

    def test_ui_strings_do_not_reference_deleted_tabs(self):
        _needles = tuple(_DEAD_UI_REFERENCES)
        _all_hits: list[tuple[str, int, str, str]] = []
        for _py in sorted((_ROOT / 'src/ui').rglob('*.py')):
            _all_hits.extend(_scan_string_literals(_py, _needles))
        if _all_hits:
            _why = '\n'.join(f'  「{_k}」→ {_v}'
                             for _k, _v in _DEAD_UI_REFERENCES.items())
            pytest.fail(_format_hits(_all_hits) + '\n禁用理由：\n' + _why)

    def test_etf_backtest_module_really_gone(self):
        """佐證：不是只有文案改乾淨，模組與 re-export 都確實不存在。

        用靜態解析而非 `import etf_dashboard` —— 那個 shim 會把整條
        data/compute/render 依賴鏈拉進來，在 streamlit stub 下太脆弱，
        會製造與本議題無關的假紅燈。
        """
        assert not (_ROOT / 'src/ui/etf/etf_tab_backtest.py').exists(), \
            'etf_tab_backtest.py 又出現了；若是刻意復活，請同步改回相關文案。'
        _dash = (_ROOT / 'src/ui/etf/etf_dashboard.py').read_text(encoding='utf-8')
        _imported = {
            _a.name
            for _n in ast.walk(ast.parse(_dash))
            if isinstance(_n, ast.ImportFrom)
            for _a in _n.names
        }
        assert not {_n for _n in _imported if 'backtest' in _n.lower()}, (
            'etf_dashboard 又 re-export 了 backtest 相關入口。'
        )

    def test_etf_backtest_session_key_has_no_writer(self):
        """`etf_backtest_data` 只有讀者沒有寫者 → 文案不可宣傳這項輸入。

        若哪天真的接回回測（出現 writer），本測試會紅，提醒把 etf_tab_ai
        那段「本系統目前沒有回測功能」的說明改回來。
        """
        _assign_re = re.compile(
            r"session_state\[['\"]etf_backtest_data['\"]\]\s*=(?!=)")
        _writers: list[str] = []
        for _py in sorted((_ROOT / 'src').rglob('*.py')):
            for _i, _line in enumerate(
                    _py.read_text(encoding='utf-8').splitlines(), 1):
                if _assign_re.search(_line):
                    _writers.append(f'{_py}:{_i}  {_line.strip()}')
        assert not _writers, (
            'etf_backtest_data 出現寫入者：\n' + '\n'.join(_writers) +
            '\n→ 請同步把 etf_tab_ai.py 的「本系統目前沒有回測功能」說明改回來。'
        )


# ════════════════════════════════════════════════════════════════
# 9. 型態學：宣稱的型態集合 == pattern_targets 真的會回的型態
# ════════════════════════════════════════════════════════════════

class TestPatternDocParity:

    def test_head_and_shoulders_is_labelled_as_not_implemented(self):
        """系統只判三種型態，頭肩底不在其中 —— 教材段必須標明未實作。"""
        import src.compute.strategy.pattern_targets as _pt
        _src = pathlib.Path(_pt.__file__).read_text(encoding='utf-8')
        assert '頭肩底' not in _src, (
            'pattern_targets 出現「頭肩底」—— 若真的實作了，'
            '請把教學頁「系統未實作」那句拿掉。'
        )
        _edu = (_ROOT / 'src/ui/tabs/tab_edu.py').read_text(encoding='utf-8')
        _idx = _edu.find('頭肩底（Inverse Head & Shoulders）')
        assert _idx > 0, '找不到頭肩底章節標題（可能被改寫過）'
        _heading = _edu[_idx:_idx + 120]
        assert '未實作' in _heading, (
            '頭肩底章節標題沒有標「系統未實作」—— 使用者會在畫面上找這個功能。'
        )

    def test_breakdown_reversal_rule_is_price_only(self):
        """行為斷言：破底翻判定不看量（教學頁據此說明「量價確認要自己補」）。"""
        from src.compute.strategy.pattern_targets import derive_pattern_levels
        _swings = [
            {'idx': 0, 'kind': 'low',  'price': 100.0},   # 支撐 / 前低
            {'idx': 1, 'kind': 'high', 'price': 120.0},
            {'idx': 2, 'kind': 'low',  'price': 90.0},    # 破底
        ]
        # 現價站回支撐之上 → 破底翻（完全沒有成交量參與判定）
        _r = derive_pattern_levels(_swings, current_price=105.0)
        assert _r is not None and _r['pattern'] == '破底翻'
        # 現價仍在支撐之下 → 不成立
        _r2 = derive_pattern_levels(_swings, current_price=95.0)
        assert _r2 is not None and _r2['pattern'] != '破底翻'
