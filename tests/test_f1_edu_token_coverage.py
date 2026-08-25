"""F1 v19.184 — 說明導引 token 覆蓋 + 門檻手抄守衛。

【這批守衛在防什麼】
使用者要的是「用清晰分類與導引說明降低理解門檻」。分類已完成；**導引說明**
這一半的病灶是同一個：

    可被 code 證實或證偽的門檻數字，被**手打**進 `help=` / `st.caption` /
    教學卡文案裡 → 判定式改了、說明沒改 → 畫面自己打自己。

已發生過的（都已修，本檔釘住不准復發）：
  1. 融資 2600 億時，總經頁融資卡印「🟡 警戒」、說明書教學卡印「🔴 散戶過熱」
     —— 教學卡手寫「> 2500 億 = 🔴」，判定 SSOT 是 2500 黃 / 3400 紅（B7）。
  2. `tab_edu` 教學卡的 sparkline 閾值線是**第四組**手打數字：`^TNX (4, 5)`
     vs SSOT 4.5/5.0 —— 同一張卡上，趨勢圖的線與判讀表的門檻不一致（F1）。
     逐條比對後 8 條有 6 條對不上（NAPM 45 vs 46、CPI 混兩把尺、M1B-M2、外資現貨…）。
  3. `PICKER_S1_MIN_PASS` 由 5 改 6 時，同檔三處 caption 都改了，
     **只有餵給 AI 的統計沒改** → 送進 LLM 的篩選標準是假的（v18.466 → v19.178）。

【設計原則（本 session 吃過虧才寫下來的）】
- **優先行為斷言**：建構輸入 → 呼叫 production 函式 → 驗結果。
  例：`edu_threshold_lines('^TNX')` 直接跟 `SPECS_BY_KEY['us10y']` 對答案，
  而不是斷言它等於 `4.5` —— 後者是把同一個數字抄第三份，漂移時三份一起錯。
- **不照抄實作字面**：token 的值一律**解析回數字**再跟 SSOT 常數比，
  不比格式化後的字串。這樣「改了顯示格式」不會假紅燈，
  「改了數字沒改另一邊」才會真紅燈。
- **要掃原始碼就用 AST**：`ast` 天然看不到註解；docstring（含 attribute
  docstring）顯式排除；失敗訊息一律印 `file:line` + 該行原文 **+ 可直接貼上的
  白名單條目**——本 session 已被「無從查起的假紅燈」擋過 8 次，
  守衛難用到讓人想關掉，就等於沒有守衛。
"""
from __future__ import annotations

import ast
import math
import pathlib
import re
import sys
import types

import pytest

from shared.fred_series import FRED_NAPM as _FRED_NAPM

_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: `§§TOKEN§§` 佔位符樣式（與 `shared.edu_tokens.TOKEN_PATTERN` 同一約定）
_TOKEN_RE = re.compile(r'§§[A-Z0-9_]+§§')

#: 解析文字裡的（帶正負號）十進位數字，供「圖上的線是否也出現在同卡表格」對帳
_NUM_RE = re.compile(r'-?\d+(?:\.\d+)?')


def _as_number(token_value: object) -> float:
    """把 token 的**顯示字串**解析回數字（`'2,500'` → `2500.0`、`'+30'` → `30.0`）。

    刻意不比字串：格式（千分位 / 正負號 / 小數位）是顯示決策，
    數值才是「使用者看到的門檻是不是真的那條線」。
    """
    return float(str(token_value).replace(',', '').replace('−', '-'))


# ════════════════════════════════════════════════════════════════
# streamlit stub —— 與 tests/test_b6a_edu_doc_parity.py 同模式（進出各一次）
# 只有「要 import L5 `tab_edu`」的測試需要；L0 / L1 的測試不碰它。
# ════════════════════════════════════════════════════════════════

def _install_streamlit_stub() -> None:
    _mod = types.ModuleType('streamlit')
    _mod._is_test_stub = True

    def _noop(*a, **k):
        return None

    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    for _name in ('divider', 'info', 'success', 'warning', 'error', 'metric',
                  'code', 'plotly_chart', 'dataframe', 'markdown', 'caption'):
        setattr(_mod, _name, _noop)
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


@pytest.fixture(scope='module')
def tab_edu_mod():
    """在 streamlit stub 下 import L5 `tab_edu`，退出時還原（避免污染其他測試）。"""
    import importlib

    # ① 先在**真 streamlit** 下把整棵樹 import 起來。
    #    `src/ui/tabs/__init__.py` 是 eager barrel(docstring 雖寫 "PEP 562 lazy"
    #    但頂上那行 `from . import (...)` 是立即的),它會連鎖拉進 `src/ui/pages/`,
    #    於是「import 一個 tab」= 首次 import 近千個模組。若在 stub 視窗內做這件事,
    #    那近千個模組的 module-level `st` 會**永久**綁在待丟棄的 stub 上。
    #    先行 import 讓 stub 視窗內不會有任何「首次 import」。
    import src.ui.tabs.tab_edu  # noqa: F401 — 只為觸發 import,不取用符號
    from tests.conftest import rebind_modules_bound_to

    _saved = sys.modules.get('streamlit')
    _install_streamlit_stub()
    _stub = sys.modules['streamlit']
    importlib.reload(sys.modules['src.ui.tabs.tab_edu'])
    try:
        import src.ui.tabs.tab_edu as _mod
        yield _mod
    finally:
        if _saved is not None:
            sys.modules['streamlit'] = _saved
        else:
            sys.modules.pop('streamlit', None)
        # ② 補漏:視窗內若仍有模組綁到 stub(例如測試執行中才觸發的函式內 import),
        #    針對性 reload 它們。不是無差別 reload 全樹。
        rebind_modules_bound_to(_stub)


# ════════════════════════════════════════════════════════════════
# 1. token 解析行為 —— 建構輸入 → 呼叫 → 驗結果
# ════════════════════════════════════════════════════════════════

class TestResolveBehaviour:

    def test_every_registered_token_resolves_away(self):
        """把所有已登記 token 串成一段文字丟進去，出來不得殘留任何 `§§`。

        這是「畫面上不會印出 §§XXX§§ 亂碼」的直接行為驗證。
        """
        from shared.edu_tokens import edu_tokens, resolve_edu_tokens

        _tokens = edu_tokens()
        assert _tokens, 'edu_tokens() 回空 dict —— 整個機制等於沒接上'
        _doc = ' ｜ '.join(f'X{_k}Y' for _k in _tokens)
        _out = resolve_edu_tokens(_doc)
        _left = sorted(set(_TOKEN_RE.findall(_out)))
        assert not _left, (
            f'下列 token 已登記卻沒被替換掉（取代邏輯壞了）：{_left}'
        )
        assert '§§' not in _out, f'仍有殘留的 §§ 片段：{_out[:200]!r}'

    def test_unregistered_token_is_kept_verbatim_and_reported(self):
        """未登記的 token **必須原樣留在畫面上**（§1 降級不靜默），且可被查出。

        反例（本守衛要擋的退化）：有人把 `resolve_edu_tokens` 改成
        「查不到就換成空字串」—— 畫面看起來乾淨，但門檻整個消失，
        使用者讀到一句沒有數字的判讀規則，比印出亂碼危險得多。
        """
        from shared.edu_tokens import resolve_edu_tokens, unresolved_tokens

        _src = '融資餘額超過 §§NO_SUCH_TOKEN_F1§§ 億 → 🔴'
        _out = resolve_edu_tokens(_src)
        assert _out == _src, '未登記的 token 被吃掉了（應原樣保留）'
        assert unresolved_tokens(_out) == {'§§NO_SUCH_TOKEN_F1§§'}

    def test_no_token_resolves_to_empty_or_missing_marker(self):
        """每個 token 都要解出一個**看得懂的值**：非空、且不是 `⟪MISSING-…⟫`。

        `⟪MISSING-SPEC:xxx⟫` 是 `_spec()` 的 fail-loud 標記 —— 它出現在
        正式 token 表裡，代表某個 spec key 打錯字，畫面會印出那串怪符號。
        """
        from shared.edu_tokens import edu_tokens

        _bad = {_k: _v for _k, _v in edu_tokens().items()
                if not str(_v).strip() or '⟪MISSING' in str(_v)}
        assert not _bad, (
            f'下列 token 解不出值（空字串或 fail-loud 標記），畫面會出現怪符號：\n'
            + '\n'.join(f'  {_k} → {_v!r}' for _k, _v in sorted(_bad.items()))
        )

    def test_every_l0_token_value_is_a_number(self):
        """L0 token 的值**全部**是數字（門檻），沒有例外。

        L0 只放「純 L0 常數推得的門檻」；文字型 token（如 PMI 來源名單）
        依設計住在 L5（見 `shared/edu_tokens` docstring）。
        若哪天 L0 冒出一個非數字 token，八成是有人把 L1 衍生的東西搬錯層。
        """
        from shared.edu_tokens import edu_tokens

        _bad = []
        for _k, _v in edu_tokens().items():
            try:
                _as_number(_v)
            except ValueError:
                _bad.append(f'  {_k} → {_v!r}')
        assert not _bad, (
            '下列 L0 token 的值不是數字。L0 token 表只該放門檻數字；'
            '需要 L1 才算得出的（例：PMI 來源名單）請放 '
            '`tab_edu._l1_derived_edu_tokens()`：\n' + '\n'.join(_bad)
        )

    def test_resolve_edu_rules_substitutes_both_columns(self):
        from shared.edu_tokens import resolve_edu_rules

        _out = resolve_edu_rules([
            ['< §§MARGIN_WARN_YI§§ 億', '🟢 安全（紅線 §§MARGIN_OVERHEAT_YI§§）'],
        ])
        assert len(_out) == 1
        assert isinstance(_out[0], tuple) and len(_out[0]) == 2
        assert '§§' not in _out[0][0] + _out[0][1], (
            'how_to_read 的「門檻」與「判讀」兩欄都必須做 token 取代，'
            f'實際得到 {_out[0]!r}'
        )

    def test_resolve_edu_rules_drops_bad_row_loudly(self, capsys):
        """壞掉的列要**出聲**再跳過 —— 靜默丟掉的話畫面只是少一列，沒人會發現。"""
        from shared.edu_tokens import resolve_edu_rules

        _out = resolve_edu_rules([['只有一欄'], ['門檻', '判讀']])
        assert _out == [('門檻', '判讀')]
        assert '⚠️' in capsys.readouterr().out, (
            '結構壞掉的 how_to_read 列被靜默略過（§1：降級必須看得見）'
        )

    def test_resolve_edu_rules_empty_input(self):
        from shared.edu_tokens import resolve_edu_rules
        assert resolve_edu_rules(None) == []
        assert resolve_edu_rules([]) == []

    def test_lookup_helpers_fail_loud(self):
        """查不到就回**看得見的錯誤標記**，不得回空字串或 0（§1）。"""
        from shared.edu_tokens import _band, _spec

        assert _spec('no_such_bucket_key', 'yellow').startswith('⟪MISSING-SPEC')
        assert _spec('vix', 'no_such_field').startswith('⟪MISSING-FIELD')
        assert _band([], 'yellow').startswith('⟪MISSING-BAND')
        assert _band([(1.0, 'green')], 'red').startswith('⟪MISSING-BAND')


# ════════════════════════════════════════════════════════════════
# 2. token 的「值」== SSOT 的值（解析回數字再比，不比字面）
# ════════════════════════════════════════════════════════════════

def _expected_token_numbers() -> dict[str, float]:
    """token → 它**應該**等於的 SSOT 數字（現場從 SSOT 取，不是抄常值）。"""
    from shared.macro_buckets import SPECS_BY_KEY
    from shared.signal_thresholds import (
        BREADTH_BULL_PCT,
        BREADTH_NEUTRAL_PCT,
        ETF_QUICK_SIGMA_CHEAP,
        ETF_QUICK_SIGMA_DISASTER,
        ETF_QUICK_SIGMA_HIGH,
        ETF_QUICK_SIGMA_OVERBOUGHT,
        ETF_QUICK_SIGMA_OVERSOLD,
        FOREIGN_5D_NET_THRESHOLD_YI,
        FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD,
        FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS,
        FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS,
        HEALTH_WEIGHT_JQ,
        HEALTH_WEIGHT_SCORE,
        MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI,
        MARGIN_BALANCE_WARN_THRESHOLD_YI,
        RECESSION_LOGIT_COEF_INTERCEPT,
        RECESSION_LOGIT_COEF_SPREAD,
        TNX_NEUTRAL_PCT,
        TOP5_LARGE_TRADER_NET_BULL_LOTS,
        TOP5_LARGE_TRADER_NET_WARN_LOTS,
        TWII_20D_DROP_THRESHOLD_PCT,
        US_CORE_CPI_YOY_BANDS,
        VIX_HIGH_RISK_THRESHOLD,
        VIX_MEDIUM_RISK_THRESHOLD,
    )
    from shared.thresholds import YIELD_HIGH, YIELD_LOW, YIELD_MID
    from src.config import LEEK_ALERT_HIGH_PCT, LEEK_ALERT_LOW_PCT

    def _sp(key: str, field: str) -> float:
        return float(getattr(SPECS_BY_KEY[key], field))

    def _bd(level: str) -> float:
        return float(next(b[0] for b in US_CORE_CPI_YOY_BANDS if b[1] == level))

    return {
        '§§MARGIN_WARN_YI§§': float(MARGIN_BALANCE_WARN_THRESHOLD_YI),
        '§§MARGIN_OVERHEAT_YI§§': float(MARGIN_BALANCE_OVERHEAT_THRESHOLD_YI),
        '§§FUT_YELLOW_LOTS§§': float(FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS),
        '§§FUT_RED_LOTS§§': float(FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS),
        '§§FUT_V4_YELLOW_LOTS§§': float(FOREIGN_FUTURES_MEDIUM_RISK_THRESHOLD_LOTS),
        '§§FUT_V4_RED_LOTS§§': float(FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS),
        '§§FUT_DEFENSE_LOTS§§': float(FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD),
        '§§TOP5_WARN_LOTS§§': float(TOP5_LARGE_TRADER_NET_WARN_LOTS),
        '§§TOP5_BULL_LOTS§§': float(TOP5_LARGE_TRADER_NET_BULL_LOTS),
        '§§TOP5_WARN_LOTS_ABS§§': abs(float(TOP5_LARGE_TRADER_NET_WARN_LOTS)),
        '§§VIX_YELLOW§§': _sp('vix', 'yellow'),
        '§§VIX_RED§§': _sp('vix', 'red'),
        '§§CPI_YELLOW§§': _sp('us_core_cpi', 'yellow'),
        '§§CPI_RED§§': _sp('us_core_cpi', 'red'),
        '§§US10Y_YELLOW§§': _sp('us10y', 'yellow'),
        '§§US10Y_RED§§': _sp('us10y', 'red'),
        '§§DXY_YELLOW§§': _sp('dxy', 'yellow'),
        '§§DXY_RED§§': _sp('dxy', 'red'),
        '§§TW_EXPORT_YELLOW§§': _sp('tw_export', 'yellow'),
        '§§TW_EXPORT_RED§§': _sp('tw_export', 'red'),
        '§§FOREIGN_NET_YELLOW_YI§§': _sp('foreign_net', 'yellow'),
        '§§FOREIGN_NET_RED_YI§§': _sp('foreign_net', 'red'),
        '§§M1B_M2_YELLOW§§': _sp('m1b_m2_gap', 'yellow'),
        '§§M1B_M2_RED§§': _sp('m1b_m2_gap', 'red'),
        '§§PMI_YELLOW§§': _sp('ism_pmi', 'yellow'),
        '§§PMI_RED§§': _sp('ism_pmi', 'red'),
        '§§HEALTH_YELLOW§§': _sp('health', 'yellow'),
        '§§HEALTH_RED§§': _sp('health', 'red'),
        '§§BIAS240_YELLOW§§': _sp('bias_240', 'yellow'),
        '§§BIAS240_RED§§': _sp('bias_240', 'red'),
        '§§CPI_MID_YELLOW§§': _bd('yellow'),
        '§§CPI_MID_RED§§': _bd('red'),
        '§§VIX_V4_YELLOW§§': float(VIX_MEDIUM_RISK_THRESHOLD),
        '§§VIX_V4_RED§§': float(VIX_HIGH_RISK_THRESHOLD),
        '§§TNX_NEUTRAL§§': float(TNX_NEUTRAL_PCT),
        '§§FOREIGN_5D_YI§§': float(FOREIGN_5D_NET_THRESHOLD_YI),
        '§§YIELD_HIGH§§': float(YIELD_HIGH),
        '§§YIELD_MID§§': float(YIELD_MID),
        '§§YIELD_LOW§§': float(YIELD_LOW),
        '§§BREADTH_BULL§§': float(BREADTH_BULL_PCT),
        '§§BREADTH_NEUTRAL§§': float(BREADTH_NEUTRAL_PCT),
        '§§TWII_20D_PCT§§': float(TWII_20D_DROP_THRESHOLD_PCT),
        '§§LEEK_ALERT_HIGH§§': float(LEEK_ALERT_HIGH_PCT),
        '§§LEEK_ALERT_LOW§§': float(LEEK_ALERT_LOW_PCT),
        '§§RECESSION_COEF_SPREAD§§': float(RECESSION_LOGIT_COEF_SPREAD),
        '§§RECESSION_COEF_INTERCEPT§§': float(RECESSION_LOGIT_COEF_INTERCEPT),
        '§§HEALTH_W_JQ_PCT§§': float(HEALTH_WEIGHT_JQ) * 100,
        '§§HEALTH_W_SCORE_PCT§§': float(HEALTH_WEIGHT_SCORE) * 100,
        '§§ETF_SIGMA_DISASTER§§': float(ETF_QUICK_SIGMA_DISASTER),
        '§§ETF_SIGMA_OVERSOLD§§': float(ETF_QUICK_SIGMA_OVERSOLD),
        '§§ETF_SIGMA_CHEAP§§': float(ETF_QUICK_SIGMA_CHEAP),
        '§§ETF_SIGMA_HIGH§§': float(ETF_QUICK_SIGMA_HIGH),
        '§§ETF_SIGMA_OVERBOUGHT§§': float(ETF_QUICK_SIGMA_OVERBOUGHT),
    }


#: 這些 token 的「真值」不是一個常數，而是**一條公式**（logistic 衰退機率），
#: 已由 `tests/test_b6a_edu_doc_parity.py::TestRecessionProbability` 直接呼叫
#: production 的 `macro_core.recession_probability()` 對帳。
#: 這裡**刻意不重複斷言** —— 同一個對象由兩支測試各自寫一份預期，
#: 正是本 session 出現過「兩個 agent 對同一對象寫出互斥預期」的成因。
#: 本檔只補一條那邊沒有的性質：三個示例值必須單調（見 `test_recession_examples_are_monotone`）。
_COVERED_ELSEWHERE: frozenset[str] = frozenset({
    '§§RECESSION_P_AT_0§§',
    '§§RECESSION_P_AT_M1§§',
    '§§RECESSION_P_AT_M2§§',
})


class TestTokenValuesMatchSSOT:

    @pytest.mark.parametrize('token', sorted(_expected_token_numbers()))
    def test_token_number_equals_ssot(self, token):
        """使用者看到的數字 == 判定式用的數字（§4.3：浮點用容差，不用 `==`）。"""
        from shared.edu_tokens import edu_tokens

        _shown = edu_tokens()[token]
        _truth = _expected_token_numbers()[token]
        assert math.isclose(_as_number(_shown), _truth,
                            rel_tol=1e-9, abs_tol=1e-12), (
            f'{token} 顯示 {_shown!r}（解析為 {_as_number(_shown)}），'
            f'但 SSOT 是 {_truth} —— 兩邊已漂移。'
            f'以 SSOT 為準：修 `shared/edu_tokens.edu_tokens()` 的取值來源。'
        )

    def test_every_token_is_covered_by_this_table(self):
        """新增 token 必須同步進上面的對帳表，否則它就是「沒人在看」的第二份真相。"""
        from shared.edu_tokens import edu_tokens

        _missing = sorted(set(edu_tokens())
                          - set(_expected_token_numbers())
                          - _COVERED_ELSEWHERE)
        assert not _missing, (
            '下列 token 沒有 SSOT 對帳，等於新開了一個無人看管的數字來源。\n'
            '請在本檔 `_expected_token_numbers()` 補上它們對應的 SSOT 常數；\n'
            '若它已由別的測試對帳，改列入 `_COVERED_ELSEWHERE` 並註明是哪一支：\n'
            + '\n'.join(f'  {_t}' for _t in _missing)
        )

    def test_v4_aliases_equal_their_base_tokens(self):
        """`FUT_V4_*` 是 `FUT_*` 的別名，永遠必須相等（別名的唯一風險就是分岔）。"""
        from shared.edu_tokens import edu_tokens

        _t = edu_tokens()
        assert _t['§§FUT_V4_YELLOW_LOTS§§'] == _t['§§FUT_YELLOW_LOTS§§']
        assert _t['§§FUT_V4_RED_LOTS§§'] == _t['§§FUT_RED_LOTS§§']

    def test_recession_examples_are_monotone(self):
        """概念正確性：利差越負 → 衰退機率越高。比對值更難造假。"""
        from shared.edu_tokens import edu_tokens

        _t = edu_tokens()
        _p0 = _as_number(_t['§§RECESSION_P_AT_0§§'])
        _p1 = _as_number(_t['§§RECESSION_P_AT_M1§§'])
        _p2 = _as_number(_t['§§RECESSION_P_AT_M2§§'])
        assert _p0 < _p1 < _p2, (
            f'倒掛越深機率應越高，實際 0%→{_p0} / −1%→{_p1} / −2%→{_p2}'
        )


# ════════════════════════════════════════════════════════════════
# 3. EDU_GUIDE（L1 教學卡）不得殘留未登記 token
# ════════════════════════════════════════════════════════════════

class TestEduGuideResolves:

    def test_no_unresolved_token_in_edu_guide(self):
        from shared.edu_tokens import unresolved_tokens
        from src.data.core.data_registry import EDU_GUIDE

        _left = sorted(unresolved_tokens(EDU_GUIDE))
        assert not _left, (
            f'`data_registry.EDU_GUIDE` 用了未登記的 token {_left} —— '
            f'這些會**原樣印在教學卡上**。請到 `shared/edu_tokens.edu_tokens()` '
            f'補登記（先確認該門檻真的有 SSOT 常數，沒有的話先抽常數，§3.3）。'
        )

    def test_rendered_edu_cards_have_no_placeholder_left(self):
        """把每張卡的 `how_to_read` 真的跑一次取代，出來不得殘留 `§§`。"""
        from shared.edu_tokens import edu_tokens, resolve_edu_rules
        from src.data.core.data_registry import EDU_GUIDE

        _tk = edu_tokens()
        _bad = []
        for _ident, _card in EDU_GUIDE.items():
            for _cond, _verdict in resolve_edu_rules(_card.get('how_to_read'), _tk):
                if '§§' in _cond or '§§' in _verdict:
                    _bad.append(f'  {_ident}: {_cond!r} / {_verdict!r}')
        assert not _bad, '教學卡渲染後仍有佔位符：\n' + '\n'.join(_bad)


# ════════════════════════════════════════════════════════════════
# 4. L0 / L5 兩份 token 表的收斂（F1 決議：一份 L0 主表 + 一小撮 L1 衍生）
# ════════════════════════════════════════════════════════════════

class TestTokenTableConvergence:

    def test_l5_table_is_superset_of_l0(self, tab_edu_mod):
        from shared.edu_tokens import edu_tokens as _l0

        _missing = sorted(set(_l0()) - set(tab_edu_mod._edu_tokens()))
        assert not _missing, (
            f'`tab_edu._edu_tokens()` 少了 L0 已登記的 token {_missing} —— '
            f'它應該是 `{{**edu_tokens(), **_l1_derived_edu_tokens()}}`。'
        )

    def test_l5_does_not_override_l0_tokens(self, tab_edu_mod):
        """L5 那層**只能補**，不能覆寫 L0 —— 覆寫 = 偷偷開第二個真相。"""
        from shared.edu_tokens import edu_tokens as _l0

        _l0_tokens = _l0()
        _l5_tokens = tab_edu_mod._edu_tokens()
        _diff = {_k: (_l0_tokens[_k], _l5_tokens[_k])
                 for _k in _l0_tokens
                 if _k in _l5_tokens and _l5_tokens[_k] != _l0_tokens[_k]}
        assert not _diff, (
            '下列 token 在 L5 被覆寫成不同的值（同一個門檻兩種說法）：\n'
            + '\n'.join(f'  {_k}: L0={_a!r} vs L5={_b!r}'
                        for _k, (_a, _b) in sorted(_diff.items()))
        )

    def test_l1_derived_layer_only_holds_what_l0_cannot_reach(self, tab_edu_mod):
        """L5 那層只該放「L0 構不到」的 token。

        目前只有 PMI 多源賽跑名單需要 L1 `PMI_SOURCE_REGISTRY`
        （§8.2：L0 不得依賴 L1+）。多出來的任何一個，八成是有人又在 L5
        自己定義了一份門檻 —— 那正是 F1 收斂掉的東西。
        """
        _keys = set(tab_edu_mod._l1_derived_edu_tokens())
        assert _keys == {'§§PMI_SOURCES§§', '§§PMI_SOURCE_COUNT§§'}, (
            f'`_l1_derived_edu_tokens()` 現在有 {sorted(_keys)}。\n'
            f'新增 token 前請先問：它能不能只用 L0 常數算出來？\n'
            f'  能 → 放 `shared/edu_tokens.edu_tokens()`（唯一定義點）；\n'
            f'  不能（需要 L1/L2 取數）→ 才留這裡，並更新本測試的預期集合 + '
            f'`shared/edu_tokens` docstring 的說明。'
        )


# ════════════════════════════════════════════════════════════════
# 5. 教學卡 sparkline 閾值線 == 五桶 SSOT（^TNX 那組不一致的回歸守衛）
# ════════════════════════════════════════════════════════════════

class TestEduThresholdLines:

    def test_lines_are_derived_from_bucket_specs(self, tab_edu_mod):
        """逐個 identifier 對答案：畫在圖上的線必須就是 `BUCKET_DANGER_SPECS` 那條。

        這條取代了原本手打的 `_intl_map` / `_single` 閾值表（8 條有 6 條對不上）。
        """
        from shared.macro_buckets import SPECS_BY_KEY

        _bad = []
        for _ident, _key in tab_edu_mod._EDU_SPEC_KEY_BY_IDENTIFIER.items():
            _warn, _crit, _hib = tab_edu_mod.edu_threshold_lines(_ident)
            if _key is None:
                if (_warn, _crit, _hib) != (None, None, None):
                    _bad.append(f'  {_ident}: 登記為「無判定式」卻回了 '
                                f'{(_warn, _crit, _hib)}')
                continue
            _spec = SPECS_BY_KEY[_key]
            if _spec.direction == 'band':
                _want = (_spec.yellow, _spec.yellow_lo, None)
            else:
                _want = (_spec.yellow, _spec.red,
                         _spec.direction == 'high_bad')
            if (_warn, _crit, _hib) != _want:
                _bad.append(f'  {_ident} (spec={_key}): 得到 '
                            f'{(_warn, _crit, _hib)}，應為 {_want}')
        assert not _bad, (
            '教學卡 sparkline 的閾值線與五桶 SSOT 不一致：\n' + '\n'.join(_bad)
        )

    def test_unknown_identifier_draws_no_line(self, tab_edu_mod):
        """沒登記的 identifier **不畫線**，不得從別的指標借一條來充數（§1）。"""
        assert tab_edu_mod.edu_threshold_lines('NO_SUCH_ID') == (None, None, None)

    @pytest.mark.parametrize('identifier', [
        # 只挑「卡片判讀表用的 token 走 `_spec()` 純數字格式」的那幾張，
        # 才能用「數字有沒有出現在同一張卡」這個方式對帳。
        # 排除：'MI_MARGN'（token 帶千分位逗號，且本欄無取值；該卡的門檻另由
        #                   `tests/test_d3_toolbox_registry.py` 專門對帳）、
        #       'NDC_signal'（判讀表用的是國發會**官方**燈號分帶，屬外部事實 C 類，
        #                     與本系統的 band spec 刻意不同源）、
        #       '^SOX'（本系統無判定式，卡片明講「不亮燈」）。
        '^VIX', '^TNX', 'DX-Y.NYB', 'CPILFESL', _FRED_NAPM,
        'XTEXVA01TWM664S', 'ms1.json', 'BFI82U',
    ])
    def test_chart_lines_also_appear_in_the_same_cards_rules(
            self, tab_edu_mod, identifier):
        """**同一張教學卡上，趨勢圖的線與判讀表的門檻必須是同一個數字。**

        這是 F1 修的那個 bug 的直接反面：`^TNX` 圖上畫 4/5、表上寫 4.5/5.0，
        使用者照圖判讀會得到與表格相反的結論。

        對帳方式刻意不比字面，而是「把判讀表渲染出來、抽出所有數字、
        檢查圖上那兩條線都在裡面」—— 表格改寫法、改語序都不會假紅燈，
        只有「圖表兩邊數字真的不同」才紅。
        """
        from shared.edu_tokens import edu_tokens, resolve_edu_rules
        from src.data.core.data_registry import EDU_GUIDE

        _card = EDU_GUIDE.get(identifier)
        assert _card is not None, f'EDU_GUIDE 沒有 {identifier} 這張卡'

        _warn, _crit, _ = tab_edu_mod.edu_threshold_lines(identifier)
        assert _warn is not None and _crit is not None

        _text = ' '.join(
            f'{_c} {_v}' for _c, _v
            in resolve_edu_rules(_card.get('how_to_read'), edu_tokens())
        )
        _nums = {float(_m) for _m in _NUM_RE.findall(_text)}
        _missing = [_x for _x in (_warn, _crit)
                    if not any(math.isclose(float(_x), _n, rel_tol=1e-9,
                                            abs_tol=1e-9) for _n in _nums)]
        assert not _missing, (
            f'{identifier} 教學卡：sparkline 畫的線 {_missing} '
            f'沒有出現在同一張卡的判讀表裡。\n'
            f'判讀表渲染後的數字：{sorted(_nums)}\n'
            f'  → 圖與表用了兩把尺，使用者看圖判讀會與看表判讀矛盾。'
            f'修法：讓判讀表改用對應的 §§TOKEN§§（兩邊同源），'
            f'或修正 `_EDU_SPEC_KEY_BY_IDENTIFIER` 的對應 spec。'
        )


# ════════════════════════════════════════════════════════════════
# 6. 說明字串裡的「數字 + 單位」白名單守衛（AST，排除註解/docstring）
# ════════════════════════════════════════════════════════════════
#
# 【這條在防什麼】上面 1~5 條守的是**已經接上 SSOT 的**那些。
# 這一條守的是「明天有人又寫一句新的 caption，把門檻手抄進去」。
#
# 【為什麼是白名單而不是零容忍】並非每個「數字+單位」都是門檻：
# 歷史事件（2008 雷曼 89.5）、範例數字（如 0.2 張 = 200 股）、
# 格式化 fallback（`'0%'`）都合法。零容忍會逼人關掉守衛。
#
# 【怎麼擴大掃描範圍】—— 這是設計來會長大的：
#   1. 在 `_SCAN_FILES` 加檔案（相對路徑，用 `/`）；
#   2. 跑 `pytest tests/test_f1_edu_token_coverage.py -k handwritten`；
#   3. 失敗訊息會印出**可直接貼上**的白名單條目 + 每筆的 `file:line` 與原文；
#   4. 逐筆判斷：門檻 → 改插值（§3.3）；非門檻 → 貼進 `_ALLOWED`。
#
# ⚠️ 目前只掃「F1 已逐行驗證過殘留內容」的檔案。刻意不一次全開 ——
#    一次貼進 300 條未經判讀的白名單，等於把守衛設成永遠綠燈（本 session
#    已見過這種「照抄實作字面所以永遠測不出問題」的守衛）。
# ════════════════════════════════════════════════════════════════

#: 掃描範圍（相對 repo 根目錄，POSIX 路徑）
_SCAN_FILES: tuple[str, ...] = (
    'src/ui/tabs/tab_stock_picker.py',
    'src/ui/tabs/macro/section_warroom.py',
)

#: 「數字 + 單位」樣式。單位取本專案說明文字最常見的五種
#: （億 = 金額、口 = 期貨部位、天 = 期間、pp = 百分點、% = 比率）。
_NUM_UNIT_RE = re.compile(r'\d[\d,.]*\s*(?:億|口|天|pp|%)')

#: 已判讀為「不是門檻」的字面，格式 `<相對路徑>|<命中的字面>`。
#: 檔案內位置不影響（刻意不用行號 —— 行號一重構就過期，等於保證會失效的資訊）。
_ALLOWED: frozenset[str] = frozenset({
    # 「本次掃了 N 檔、入選率 X%」的分母為 0 時的顯示 fallback，非門檻。
    'src/ui/tabs/tab_stock_picker.py|0%',
})


def _string_literal_nodes(tree: ast.AST) -> list[ast.Constant]:
    """回傳所有「會被印出去」的字串常值節點。

    排除兩類（它們不是使用者看得到的文字）：
      - 註解 —— `ast` 天然看不到，免處理；
      - 任何**單獨成句**的字串（`ast.Expr` 包一個 str Constant）——
        涵蓋 module / class / function docstring **以及 attribute docstring**
        （常數賦值下方那段 `\"\"\"…\"\"\"` 說明，本專案大量使用）。
    """
    _skip: set[int] = set()
    for _n in ast.walk(tree):
        if (isinstance(_n, ast.Expr) and isinstance(_n.value, ast.Constant)
                and isinstance(_n.value.value, str)):
            _skip.add(id(_n.value))
    return [_n for _n in ast.walk(tree)
            if isinstance(_n, ast.Constant) and isinstance(_n.value, str)
            and id(_n) not in _skip]


def test_scan_files_exist():
    """掃描清單裡的檔案都要存在 —— 檔案改名後守衛靜默失效是最糟的失敗模式。"""
    _missing = [_f for _f in _SCAN_FILES if not (_ROOT / _f).is_file()]
    assert not _missing, (
        f'`_SCAN_FILES` 指到不存在的檔案 {_missing}（改名/搬家後請同步更新）'
    )


def test_no_new_handwritten_threshold_in_help_text():
    """說明字串裡不得出現**新的**手抄門檻（數字 + 億/口/天/pp/%）。

    f-string 的插值欄位不算命中 —— 這是刻意的正向誘因：
    把 `'>2500億'` 改成 `f'>{MARGIN_BALANCE_WARN_THRESHOLD_YI:,.0f}億'`
    之後，字串常值只剩 `'>'` 與 `'億'`，守衛自動放行。
    """
    _found: list[tuple[str, int, str, str]] = []   # (rel, lineno, match, raw)
    for _rel in _SCAN_FILES:
        _path = _ROOT / _rel
        _text = _path.read_text(encoding='utf-8')
        _lines = _text.splitlines()
        for _node in _string_literal_nodes(ast.parse(_text)):
            for _m in _NUM_UNIT_RE.findall(_node.value):
                _key = f'{_rel}|{_m}'
                if _key in _ALLOWED:
                    continue
                _ln = getattr(_node, 'lineno', 0)
                _raw = _lines[_ln - 1].strip() if 0 < _ln <= len(_lines) else ''
                _found.append((_rel, _ln, _m, _raw))

    if not _found:
        return

    _paste = sorted({f"    '{_rel}|{_m}'," for _rel, _, _m, _ in _found})
    _detail = '\n'.join(
        f'  {_ROOT / _rel}:{_ln}  命中「{_m}」\n      → {_raw}'
        for _rel, _ln, _m, _raw in _found
    )
    raise AssertionError(
        '說明字串裡出現手抄的門檻數字（數字 + 億/口/天/pp/%）：\n'
        f'{_detail}\n\n'
        '── 怎麼處理 ──────────────────────────────────────────\n'
        '① 它**是**門檻 → 改成插值（§3.3 反捏造）：\n'
        "     'X>2500億'  →  f'X>{MARGIN_BALANCE_WARN_THRESHOLD_YI:,.0f}億'\n"
        '   找不到對應常數 → 先抽一個具名常數（B 類），再插值。\n'
        '② 它**不是**門檻（歷史事件 / 範例 / 格式 fallback）→ '
        '把下面這幾行貼進本檔的 `_ALLOWED`：\n'
        + '\n'.join(_paste)
    )
