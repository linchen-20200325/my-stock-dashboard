"""tests/test_d2_macro_sections.py — D2 總經剩餘 section 全掃（v19.183）。

covers（每個 class 對應一個實際抓到的缺陷，不是為了湊測試數）：

===========================  ==========================================================
class                        釘住的缺陷
===========================  ==========================================================
TestM1bM2ProxyDetection      §3.3 幽靈 key：`m1b_m2_info['is_proxy']` 從未被寫入，
                             兩處「代理值」揭露 / 守門因此永遠不生效。
TestPivotSignalColorSsot     §2.1 色碼非 SSOT → `aggregate_pivot_families` 的嚴格比對
                             永不命中 → 「位階」群恆判中性。
TestFreshnessGateWired       §2.4 30 分鐘新鮮度閘門被 section_state 無條件重算架空。
TestNoFabricatedGetDefaults  §1 `dict.get(key, <數字>)` 捏造安全預設值（0 / 50 / 100）。
TestCondBadgeLabelIsStateful §1 徽章文案不得無條件斷言「條件成立」。
TestBreadthThresholdSsot     §3.3 同檔兩套廣度門檻（inline 70/60/40 vs SSOT 常數）。
===========================  ==========================================================

測試風格（本 session 教訓）：
- **優先寫行為斷言**。凡是能用「餵資料 → 檢查輸出」證明的，一律不寫原始碼掃描。
- 不得不寫守衛時**一律走 AST**（`ast.parse` + `ast.walk`），因此天然排除註解與
  docstring；失敗訊息一律 `ast.unparse()` 印出**該行原文** + 行號，
  而不是印「找不到某字串」——後者是本 session 被假紅燈擋了 7 次的元凶。
- 守衛斷言的是**性質**（例如「色碼必須是具名 SSOT 常數」），不是照抄實作字面值；
  照抄字面值的守衛永遠不會發現實作本身有問題。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


def _unwrap(fn, *a, **k):
    """st.cache_data 裝飾函式測試時繞過快取直接呼叫底層邏輯。"""
    return fn.__wrapped__(*a, **k)


def _parse(rel_path: str) -> tuple[ast.Module, list[str]]:
    """讀檔 → (AST, 原始行 list)。行 list 供失敗訊息印原文用。"""
    _p = _REPO / rel_path
    _src = _p.read_text(encoding='utf-8')
    return ast.parse(_src, filename=str(_p)), _src.splitlines()


def _src_of(node, lines: list[str]) -> str:
    """節點原文（優先 ast.unparse；退回原始行）。"""
    try:
        return ast.unparse(node)
    except Exception:
        _ln = getattr(node, 'lineno', 0)
        return lines[_ln - 1].strip() if 0 < _ln <= len(lines) else '<unavailable>'


# ══════════════════════════════════════════════════════════════════════════
# 2. §3.3 幽靈 key — M1B/M2 代理值偵測
# ══════════════════════════════════════════════════════════════════════════
class TestM1bM2ProxyDetection:
    """`is_proxy` 從未被任何 producer 寫進 `m1b_m2_info`。

    最關鍵的是 `test_real_producer_tier3_is_detected` —— 它走**真的**
    `fetch_m1b_m2_block()`，只 mock 最上游的 CBC 回傳，
    因此不管中間怎麼重新打包 dict，只要代理值又變得偵測不到就會紅燈。
    """

    def test_explicit_flags(self):
        from shared.macro_provenance import is_m1b_m2_proxy
        assert is_m1b_m2_proxy({'is_proxy': True}) is True
        assert is_m1b_m2_proxy({'is_proxy_tier': True}) is True
        assert is_m1b_m2_proxy({'is_proxy': False, 'source': 'CBC-tier1'}) is False

    def test_source_label(self):
        from shared.macro_provenance import (
            M1B_PROXY_SOURCE_LABEL, M1B_PROXY_SOURCE_LABEL_RAW, is_m1b_m2_proxy,
        )
        assert is_m1b_m2_proxy({'source': M1B_PROXY_SOURCE_LABEL}) is True
        assert is_m1b_m2_proxy({'source': M1B_PROXY_SOURCE_LABEL_RAW}) is True
        assert is_m1b_m2_proxy({'source': 'CBC-tier1'}) is False
        assert is_m1b_m2_proxy({'source': 'FRED'}) is False
        assert is_m1b_m2_proxy({'source': 'IMF(2025)'}) is False

    def test_missing_or_malformed_is_not_proxy(self):
        """§1 的分寸：拿不到資料 → 不宣稱它是代理值（缺資料另有守門）。"""
        from shared.macro_provenance import is_m1b_m2_proxy
        assert is_m1b_m2_proxy(None) is False
        assert is_m1b_m2_proxy({}) is False
        assert is_m1b_m2_proxy('not a dict') is False
        assert is_m1b_m2_proxy({'source': None}) is False

    def test_real_producer_tier3_is_detected(self, monkeypatch):
        """走真的 `fetch_m1b_m2_block()`：CBC 落到 Tier 3 → 必須判為代理。"""
        import src.data.macro.macro_snapshot as ms
        from shared.macro_provenance import is_m1b_m2_proxy
        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: {'m1b_yoy': 2.1, 'm2_yoy': 1.4, 'gap': 0.7,
                     'tier_used': 3, 'is_proxy_tier': True,
                     'source': 'Yahoo:^TWII:proxy_tier3'},
        )
        r = _unwrap(ms.fetch_m1b_m2_block, '')
        assert r is not None
        assert is_m1b_m2_proxy(r) is True, (
            'Tier 3（^TWII 動能代理）必須被判為代理值，否則畫面會把它印成'
            f'央行真實 M1B/M2 年增率。實得 m1b_m2_info={r}'
        )

    def test_real_producer_tier1_is_not_proxy(self, monkeypatch):
        import src.data.macro.macro_snapshot as ms
        from shared.macro_provenance import is_m1b_m2_proxy
        monkeypatch.setattr(
            'src.data.macro.fetch_cbc_m1b_m2',
            lambda: {'m1b_yoy': 1.2, 'm2_yoy': 13.83, 'gap': -12.63,
                     'tier_used': 1, 'is_proxy_tier': False},
        )
        r = _unwrap(ms.fetch_m1b_m2_block, '')
        assert is_m1b_m2_proxy(r) is False


# ══════════════════════════════════════════════════════════════════════════
# 3. §2.1 拐點訊號色碼必須是 traffic SSOT（下游做嚴格比對）
# ══════════════════════════════════════════════════════════════════════════
class TestPivotSignalColorSsot:
    """`aggregate_pivot_families` 是 `color == TRAFFIC_RED` 嚴格比對。

    先用行為斷言證明「非 SSOT 色碼會被歸成 neutral」（＝這條規則不是形式主義），
    再用 AST 保證 `section_state.py` 每一個 `pivot_signals.append` 都用具名常數。
    """

    _ALLOWED_NAMES = {'TRAFFIC_RED', 'TRAFFIC_GREEN',
                      'TRAFFIC_YELLOW', 'TRAFFIC_NEUTRAL'}

    def test_offspec_hex_is_silently_downgraded_to_neutral(self):
        """行為證明：舊色碼 '#da3633' 不會被算成偏空。"""
        from src.compute.macro import aggregate_pivot_families
        _legacy = aggregate_pivot_families(
            [('月線過熱', '⚠️', '#da3633', 'x')], evaluable={'level'})
        assert _legacy['families']['level']['side'] == 'neutral'

    def test_traffic_ssot_hex_counts_as_bear(self):
        from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED
        from src.compute.macro import aggregate_pivot_families
        _fixed = aggregate_pivot_families(
            [('月線過熱', '⚠️', TRAFFIC_RED, 'x')], evaluable={'level'})
        assert _fixed['families']['level']['side'] == 'bear'
        _fixed_bull = aggregate_pivot_families(
            [('月線超賣', '💡', TRAFFIC_GREEN, 'x')], evaluable={'level'})
        assert _fixed_bull['families']['level']['side'] == 'bull'

    def test_every_pivot_signal_uses_named_traffic_constant(self):
        """AST 守衛：色碼欄（tuple 第 3 個元素）不得是**寫死的字面 hex**。

        斷言的是**性質**（「不准把顏色寫死」）而不是某個字面值 —— 換色票時
        本測試不會假紅燈，但任何人再寫死一個 '#xxxxxx' 就會被擋下。

        允許的形式：
          - `TRAFFIC_*` 具名常數（絕大多數）
          - `TRAFFIC_RED if cond else TRAFFIC_GREEN`（三元，如月線乖離）
          - `_mk_sig['color']`（來自 `detect_cpi_fed_double_top`，該處已用 SSOT）
        不允許：任何 `str` 字面值。
        """
        tree, lines = _parse('src/ui/tabs/macro/section_state.py')
        offenders: list[str] = []
        seen = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            _f = node.func
            if not (isinstance(_f, ast.Attribute) and _f.attr == 'append'
                    and isinstance(_f.value, ast.Name)
                    and _f.value.id == 'pivot_signals'):
                continue
            if not node.args or not isinstance(node.args[0], ast.Tuple):
                continue
            _elts = node.args[0].elts
            if len(_elts) < 3:
                continue
            seen += 1
            _color = _elts[2]
            # 色碼子樹裡只要出現**看起來像色碼的** str 字面值就是寫死（涵蓋三元兩邊）。
            # ⚠️ 必須限定 `#` 開頭：原本收「任何 str 常數」會把 docstring 明文允許的
            # `_mk_sig['color']` 也判成違規 —— subscript 的 key `'color'` 本身就是
            # 一個 str 常數。守衛的 docstring 與實作互相矛盾，是本 session 反覆出現的
            # 「同一對象兩條互斥預期」。限定 `#` 後，換色票仍不假紅燈，而任何人再寫死
            # 一個 '#xxxxxx' 照樣被擋。
            _literals = [n.value for n in ast.walk(_color)
                         if isinstance(n, ast.Constant) and isinstance(n.value, str)
                         and n.value.startswith('#')]
            _names = {n.id for n in ast.walk(_color) if isinstance(n, ast.Name)}
            if _literals or (isinstance(_color, ast.Name)
                             and _color.id not in self._ALLOWED_NAMES):
                offenders.append(
                    f'  line {getattr(_color, "lineno", "?")}: '
                    f'{_src_of(_color, lines)}  '
                    f'(字面值={_literals}, 具名={sorted(_names)})\n'
                    f'      ↳ 整行原文：{_src_of(node, lines)[:160]}')
        assert seen >= 10, f'AST 只掃到 {seen} 個 pivot_signals.append，疑似解析失敗'
        assert not offenders, (
            'pivot_signals 的色碼必須用 shared.colors 具名常數 '
            f'（{sorted(self._ALLOWED_NAMES)}），否則 aggregate_pivot_families 的'
            '嚴格比對永不命中、該群恆判中性：\n' + '\n'.join(offenders))


# ══════════════════════════════════════════════════════════════════════════
# 4. §2.4 30 分鐘新鮮度閘門必須真的擋得住
# ══════════════════════════════════════════════════════════════════════════
class TestFreshnessGateWired:
    def test_stale_cache_short_circuits_before_any_recompute(self, monkeypatch):
        """show_market_data=False → 不得重算紅綠燈（也就不會蓋掉等待訊息）。

        用 `_mkt_info=None` + 非空 `cd` 讓前面兩條分支都不進入，
        於是這支測試唯一會走到的就是閘門本身；閘門若被拿掉，
        後續 `load_section_inputs(st.session_state)` / `calc_traffic_light`
        會被呼叫並失敗（無 Streamlit runtime），測試同樣紅燈。
        """
        from src.ui.tabs.macro import section_state

        def _boom(*a, **k):
            raise AssertionError(
                '新鮮度閘門失效：快取過期時仍重算了紅綠燈，'
                '會把頁頂「⏳ 燈號等待中（已過期）」蓋成一張自信的燈號卡（§2.4）')

        monkeypatch.setattr(section_state, 'calc_traffic_light', _boom)
        assert section_state.render_section_state(
            None, object(), object(), {'sentinel': 1},
            show_market_data=False) is None

    def test_signature_defaults_to_true(self):
        """預設 True：既有 positional caller / 測試不受影響。"""
        import inspect
        from src.ui.tabs.macro import section_state
        _sig = inspect.signature(section_state.render_section_state)
        assert 'show_market_data' in _sig.parameters
        assert _sig.parameters['show_market_data'].default is True

    def test_tab_macro_passes_the_flag(self):
        """AST 守衛：tab_macro 必須顯式把新鮮度旗標傳進去，否則閘門形同虛設。"""
        tree, lines = _parse('src/ui/tabs/tab_macro.py')
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == 'render_section_state']
        assert calls, 'tab_macro.py 找不到 render_section_state 呼叫'
        for _c in calls:
            _kw = {k.arg for k in _c.keywords}
            assert 'show_market_data' in _kw, (
                f'line {_c.lineno}: {_src_of(_c, lines)}\n'
                '      ↳ 缺 show_market_data → 快取過期時 section_state 仍會'
                '重算並覆寫紅綠燈（§2.4）')


# ══════════════════════════════════════════════════════════════════════════
# 5. §1 捏造預設值 — `dict.get(key, <數字>)`
# ══════════════════════════════════════════════════════════════════════════
class TestNoFabricatedGetDefaults:
    """`dict.get` 的預設值**只在 key 不存在時生效**。

    真正常見的失敗態是「node 在、值卻是 None」（例如
    `fetch_us10y_block` 全敗時回 `{'us10y': {'current': None}}`），
    此時 `.get('current', 0)` 拿到的是 **None** 而不是 0 —— 所以這種寫法
    既擋不住真的缺值，又會在 key 真的缺席時捏出一個「安全值」：
    VIX=0 → 綠燈、CPI=0 → 通膨無虞、PMI=50 → 恰好榮枯線。
    """

    #: 允許的例外：純布林旗標的預設（bool 是 int 的子類，需另外排除）。
    def _numeric_default_offenders(self, rel_path: str) -> list[str]:
        tree, lines = _parse(rel_path)
        out: list[str] = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'get'
                    and len(node.args) == 2):
                continue
            _d = node.args[1]
            if not isinstance(_d, ast.Constant):
                continue
            _v = _d.value
            if isinstance(_v, bool) or not isinstance(_v, (int, float)):
                continue
            out.append(f'  line {node.lineno}: {_src_of(node, lines)}')
        return out

    def test_cross_ai_has_no_numeric_get_defaults(self):
        offenders = self._numeric_default_offenders(
            'src/ui/tabs/macro/section_cross_ai.py')
        assert not offenders, (
            '§九 跨桶規則決策不得用 `.get(key, <數字>)` 捏造預設值 —— '
            'VIX/CPI 缺值時會直接點亮「🟢 美股平穩、無系統性風險」：\n'
            + '\n'.join(offenders))


# ══════════════════════════════════════════════════════════════════════════
# 6. §1 徽章文案不得無條件斷言
# ══════════════════════════════════════════════════════════════════════════
class TestCondBadgeLabelIsStateful:
    """`cond_badge(ok, label)` 只用**顏色**表示成立與否，文字兩態相同。

    因此把 label 寫成固定字串（例如 'G SOX/NVDA點火'）時，
    條件不成立的灰色徽章仍然寫著「點火」—— 使用者讀到的是一句斷言。
    label 必須隨狀態變化（三元 / f-string 皆可）。
    """

    def test_section_mid_badges_are_state_dependent(self):
        tree, lines = _parse('src/ui/tabs/macro/section_mid.py')
        offenders: list[str] = []
        seen = 0
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'cond_badge'):
                continue
            if len(node.args) < 2:
                continue
            seen += 1
            if isinstance(node.args[1], ast.Constant):
                offenders.append(
                    f'  line {node.lineno}: {_src_of(node, lines)}')
        assert seen >= 7, f'AST 只掃到 {seen} 個 cond_badge，疑似解析失敗'
        assert not offenders, (
            'cond_badge 的文字兩態相同（只有顏色會變），寫死字面值等於'
            '條件不成立時仍宣稱它成立：\n' + '\n'.join(offenders))


# ══════════════════════════════════════════════════════════════════════════
# 7. §3.3 廣度門檻 SSOT
# ══════════════════════════════════════════════════════════════════════════
class TestBreadthThresholdSsot:
    def test_new_constants_exist_and_are_ordered(self):
        from shared.signal_thresholds import (
            BREADTH_AD_CONTRACTION_COUNT, BREADTH_AD_DIVERGENCE_COUNT,
            BREADTH_AD_EXPANSION_COUNT, BREADTH_BULL_PCT,
            BREADTH_DIVERGENCE_INDEX_PCT, BREADTH_NEUTRAL_PCT,
            BREADTH_STRONG_BULL_PCT, PIVOT_BIAS_20_PCT, PIVOT_BIAS_240_PCT,
        )
        # 值不得漂移（這批是「抽常數、不改數值」的重構）
        assert (BREADTH_STRONG_BULL_PCT, BREADTH_BULL_PCT, BREADTH_NEUTRAL_PCT) \
            == (70.0, 60.0, 40.0)
        assert (BREADTH_AD_EXPANSION_COUNT, BREADTH_AD_CONTRACTION_COUNT,
                BREADTH_AD_DIVERGENCE_COUNT) == (200, -100, -50)
        assert BREADTH_DIVERGENCE_INDEX_PCT == 0.5
        assert (PIVOT_BIAS_240_PCT, PIVOT_BIAS_20_PCT) == (10.0, 8.0)
        # 語意上的單調性（改門檻時若把順序弄反，這裡先擋下來）
        assert BREADTH_STRONG_BULL_PCT > BREADTH_BULL_PCT > BREADTH_NEUTRAL_PCT
        assert BREADTH_AD_EXPANSION_COUNT > 0 > BREADTH_AD_DIVERGENCE_COUNT \
            > BREADTH_AD_CONTRACTION_COUNT

    def test_section_short_has_no_inline_breadth_literals(self):
        """AST 守衛：廣度判讀分支不得再出現 70 / 60 / 40 / ±50 / 200 / -100 字面值。

        只掃 `Compare` 節點的比較對象（避免誤傷版面數字如 height=200），
        並且只針對本檔實際用於廣度判讀的那幾個變數名。
        """
        tree, lines = _parse('src/ui/tabs/macro/section_short.py')
        _watch = {'_ratio2', '_adl_ratio', '_ad2', '_adl_ad',
                  '_twii_pct2', '_twii_pct'}
        _banned = {70, 60, 40, 50, -50, 200, -100, 0.5, -0.5}
        offenders: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            _names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            if not (_names & _watch):
                continue
            for _cmp in node.comparators:
                _v = None
                if isinstance(_cmp, ast.Constant):
                    _v = _cmp.value
                elif (isinstance(_cmp, ast.UnaryOp)
                      and isinstance(_cmp.op, ast.USub)
                      and isinstance(_cmp.operand, ast.Constant)):
                    _v = -_cmp.operand.value
                if isinstance(_v, bool) or not isinstance(_v, (int, float)):
                    continue
                if _v in _banned:
                    offenders.append(
                        f'  line {node.lineno}: {_src_of(node, lines)}')
        assert not offenders, (
            '廣度判讀門檻必須走 shared/signal_thresholds SSOT —— 同檔已有'
            'BREADTH_* 常數，再寫 inline 字面值就是「改一邊漏一邊」：\n'
            + '\n'.join(offenders))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
