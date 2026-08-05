"""tests/test_p0d_veto_and_leek.py — v19.176 P0-D 守門測試。

修的是什麼
----------
**修正一｜同一頁兩個「v4.0 總經否決權」給出相反結論**（2026-08-05 實機同一次渲染）::

    §八 總經拼圖（section_mid）  → ✅ v4.0 總經否決權：無觸發
    §三 籌碼    （section_chips）→ 🏛️ v4.0 總經否決權 🔴 紅燈 — 總經環境高風險

根因不是計算錯誤，是**命名衝突**：兩者根本不是同一個判定。

  - `section_mid` 的是一組 inline 規則（VIX≥30／台灣 PMI<48／美國核心 CPI>4%／
    台灣出口 YoY<-5%／NDC≤16），**完全不看外資期貨**，也從未呼叫 `V4StrategyEngine`。
  - `section_chips` 的才是真正的 `V4StrategyEngine.check_macro_veto()`（L2 Task 2），
    只看 VIX + 外資期貨口數（門檻 SSOT：`shared/signal_thresholds`
    `VIX_HIGH_RISK_THRESHOLD=25` / `FOREIGN_FUTURES_HIGH_RISK_THRESHOLD_LOTS=-20000`）。

當日 VIX < 30（基本面側不觸發）+ 外資期貨空單 < -20,000 口（v4 側紅燈）→
兩邊各自都算對了，錯的是它們頂著同一個名字。

處置（**判定邏輯與門檻零變更**）：① 正名（名稱走 L0 SSOT `config.VETO_*`）；
② 各自標明判定範圍；③ 兩者結論不一致時**主動揭露**（§1：不一致本身必須可見，
不可挑一個顯示）；④ 取數 + 判定收斂成單一入口 `section_chips.read_v4_macro_veto()`，
確保兩區吃同一份 VIX / 外資期貨。

**修正二｜韭菜指數四套門檻並存**（只做 SSOT 化，**不改行為**）::

    config.LEEK_HIGH/LOW_THRESHOLD   35 / 10    0 consumer（且**不同量綱**，見下）
    section_chips 進階警示           >30 / <-30
    section_chips 籌碼綜合判斷        >10 / <-5   （正負不對稱）
    section_state 拐點六大面向        >20 / <-20

四組 inline magic number 全部抽到 `src/config/config.py`，**分別命名**
（`LEEK_ALERT_*` / `LEEK_SCORE_*` / `LEEK_PIVOT_*`）——
讓「同數字不同義」不會在未來被誰看到重複值就順手合併（§3.3）。

⚠️ 特別注意（§4.1 量綱陷阱）：`LEEK_HIGH_THRESHOLD=35` **不是**「還沒接線的
同一套門檻」，而是**另一個指標**的門檻 ——
  (A) 融資餘額 5Y 標準化指數，值域 [0,100]、中位 50（tab_edu.py:955-970 的公式與
      2000/4=48…2024/7=35 歷史校準表）；
  (B) 畫面上真正在跑的是小台**法人空多比**，值域約 [-100,+100]、中位 0
      （leading_indicators.py:648-726）。
把 35 拿去統一 (B) 的門檻 = 拿 0~100 的指數去比 ±% 的比值，是量綱錯誤。

本檔守門
--------
A. 否決權：兩個名稱不得再撞名、單一取數入口、分歧揭露必須存在。
B. 韭菜：門檻不得再 inline、常數值不得被悄悄改動（行為凍結）、
   兩種量綱的常數不得互相引用。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MACRO_DIR = _REPO_ROOT / 'src' / 'ui' / 'tabs' / 'macro'
_SECTION_CHIPS = _MACRO_DIR / 'section_chips.py'
_SECTION_STATE = _MACRO_DIR / 'section_state.py'
_SECTION_MID = _MACRO_DIR / 'section_mid.py'

# 舊的、造成同頁矛盾的曖昧標籤。只要它再次出現在**會渲染給使用者**的字串裡，
# 就代表正名被回退了。
_AMBIGUOUS_LABEL = 'v4.0 總經否決權'


# ── 共用小工具 ────────────────────────────────────────────────────
def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding='utf-8'), filename=str(path))


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """所有 docstring / 裸字串陳述式的 id()，用來把說明文字排除在掃描外。

    註解與 docstring 記錄「原本叫什麼、為何改掉」是好事，不該被罰；
    但**同一段文字若出現在 f-string / st.markdown 的引數裡就會渲染給使用者**，
    那就必須抓（同 `test_no_hardcoded_position_pct.py` 的設計理由）。
    """
    _ids: set[int] = set()
    for _node in ast.walk(tree):
        if (isinstance(_node, ast.Expr)
                and isinstance(_node.value, ast.Constant)
                and isinstance(_node.value.value, str)):
            _ids.add(id(_node.value))
    return _ids


def _rendered_strings(path: Path) -> list[str]:
    """回傳所有「非 docstring」的字串常值（含 f-string 的常值片段）。"""
    _t = _tree(path)
    _skip = _docstring_nodes(_t)
    return [_n.value for _n in ast.walk(_t)
            if isinstance(_n, ast.Constant) and isinstance(_n.value, str)
            and id(_n) not in _skip]


def _names(path: Path) -> set[str]:
    """回傳原始碼中真正被當成識別字使用的名字（註解 / 字串不算）。"""
    _out: set[str] = set()
    for _n in ast.walk(_tree(path)):
        if isinstance(_n, ast.Name):
            _out.add(_n.id)
        elif isinstance(_n, ast.Attribute):
            _out.add(_n.attr)
        elif isinstance(_n, ast.alias):
            _out.add(_n.name.split('.')[-1])
    return _out


def _numeric(node: ast.AST) -> float | None:
    """把 `30` / `-30` / `30.0` 這類數值常值解出來（`-30` 是 UnaryOp）。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        _inner = _numeric(node.operand)
        if _inner is not None:
            return -_inner if isinstance(node.op, ast.USub) else _inner
    return None


# ══════════════════════════════════════════════════════════════════
# A. 修正一 — v4.0 總經否決權同頁矛盾
# ══════════════════════════════════════════════════════════════════
def test_two_veto_judgements_have_distinct_names():
    """兩個判定必須有各自的名字，且互不為子字串。

    互不為子字串很重要：若一邊叫「總經否決權」、另一邊叫「v4.0 總經否決權」，
    使用者在畫面上仍會把它們讀成同一件事的兩種寫法 —— 那正是這次事故的形狀。
    """
    from src.config import VETO_FUNDAMENTAL_NAME, VETO_V4_ENGINE_NAME
    assert VETO_FUNDAMENTAL_NAME and VETO_V4_ENGINE_NAME
    assert VETO_FUNDAMENTAL_NAME != VETO_V4_ENGINE_NAME
    assert VETO_FUNDAMENTAL_NAME not in VETO_V4_ENGINE_NAME
    assert VETO_V4_ENGINE_NAME not in VETO_FUNDAMENTAL_NAME


def test_scope_notes_cross_reference_each_other():
    """兩張卡的範圍說明必須**互相指路**，使用者才知道另一半在哪、看的是什麼。

    只改名不指路仍然會被誤讀成「系統前後不一」；§1 要求不一致可見，
    「可見」包含「找得到對照的那一邊」。
    """
    from src.config import (
        VETO_FUNDAMENTAL_NAME, VETO_FUNDAMENTAL_SCOPE_NOTE,
        VETO_V4_ENGINE_NAME, VETO_V4_ENGINE_SCOPE_NOTE,
    )
    assert VETO_V4_ENGINE_NAME in VETO_FUNDAMENTAL_SCOPE_NOTE, \
        '基本面檢查的範圍說明沒有指向 v4 引擎風險燈'
    assert VETO_FUNDAMENTAL_NAME in VETO_V4_ENGINE_SCOPE_NOTE, \
        'v4 引擎風險燈的範圍說明沒有指向總經基本面否決檢查'


@pytest.mark.parametrize('path', [_SECTION_MID, _SECTION_CHIPS],
                         ids=['section_mid', 'section_chips'])
def test_ambiguous_veto_label_never_rendered(path: Path):
    """曖昧標籤「v4.0 總經否決權」不得再出現在會渲染的字串裡。

    註解與 docstring 允許保留（它們記錄事故本身），故掃描已排除 docstring；
    註解在 AST 裡本來就不存在。
    """
    _hits = [_s for _s in _rendered_strings(path) if _AMBIGUOUS_LABEL in _s]
    assert not _hits, (
        f'{path.name} 又出現會渲染的曖昧標籤 {_AMBIGUOUS_LABEL!r}：{_hits}\n'
        '兩個判定必須用 config.VETO_FUNDAMENTAL_NAME / VETO_V4_ENGINE_NAME 分名。'
    )


def test_v4_engine_has_single_entry_point():
    """v4 引擎的取數 + 判定只能有一個入口。

    §2.1 SSOT：`section_mid` 要揭露分歧，就必須跟 `section_chips` 吃**同一份**
    VIX 與外資期貨口數。若它自己再組一次 `V4StrategyEngine`，兩邊很容易各讀各的
    （例如一邊吃 ffill 後的末筆、一邊吃原始 NaN）→ 揭露分歧本身變成新的分歧來源。
    """
    _chips_src = _SECTION_CHIPS.read_text(encoding='utf-8')
    assert 'def read_v4_macro_veto(' in _chips_src, \
        'section_chips 必須提供 read_v4_macro_veto() 作為唯一入口'

    _mid_names = _names(_SECTION_MID)
    assert 'read_v4_macro_veto' in _mid_names, \
        'section_mid 必須透過 read_v4_macro_veto() 取 v4 燈號，不可自己算'
    assert 'V4StrategyEngine' not in _mid_names, (
        'section_mid 直接碰了 V4StrategyEngine —— 這會再生出第二套輸入組裝邏輯，'
        '請一律走 section_chips.read_v4_macro_veto()。'
    )


def test_divergence_between_two_judgements_is_disclosed():
    """兩套判定結論相反時，`section_mid` 必須主動揭露，而不是各印各的。

    §1：可能不一致的兩件事，不可以隨便挑一個顯示 —— 必須讓不一致本身可見。
    這裡用結構檢查（有沒有「比較兩邊結論 → 走揭露分支」）而非字串比對，
    避免文案微調就假紅。
    """
    _src = _SECTION_MID.read_text(encoding='utf-8')
    assert 'read_v4_macro_veto()' in _src
    # 有比較兩邊結論的動作
    assert '_v4_risk != _has_veto' in _src, (
        'section_mid 沒有比較「基本面是否觸發」與「v4 燈是否非綠」——'
        '沒有比較就不可能揭露分歧。'
    )
    # 且分歧時真的有輸出（st.warning）
    _tree_mid = _tree(_SECTION_MID)
    _warns = [_n for _n in ast.walk(_tree_mid)
              if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
              and _n.func.attr == 'warning']
    assert _warns, 'section_mid 沒有任何 st.warning —— 分歧揭露不會被使用者看到'


# ══════════════════════════════════════════════════════════════════
# A2. read_v4_macro_veto() 行為（含 §1 Fail Loud）
# ══════════════════════════════════════════════════════════════════
class _FakeST:
    """只提供 `session_state` 的極簡 streamlit 替身。

    `read_v4_macro_veto()` 是純讀取 + 呼叫 L2 引擎，不碰任何 UI API，
    故替身只需要一個 dict 即可 —— 若未來它長出 `st.markdown` 之類的 UI 呼叫，
    這裡會 AttributeError 而 fail，正好也是一道「別把 UI 混進取數函式」的守門。
    """

    def __init__(self, session_state: dict):
        self.session_state = session_state


def _call_read_veto(monkeypatch, session_state: dict):
    from src.ui.tabs.macro import section_chips
    monkeypatch.setattr(section_chips, 'st', _FakeST(session_state))
    return section_chips.read_v4_macro_veto()


def test_read_veto_returns_none_when_vix_missing(monkeypatch):
    """§1 Fail Loud：VIX 取不到一律回 None，**不得**回填 15。

    `V4StrategyEngine.check_macro_veto()` 內部是 `float(self.macro.get('vix') or 15)`，
    傳 None 進去會被它悄悄換成 15 → 以捏造的資料點亮綠燈。
    這是 v19.170 P0-2 修過一次的坑，抽成函式後必須守住。
    """
    assert _call_read_veto(monkeypatch, {}) is None
    assert _call_read_veto(monkeypatch, {'macro_info': {}}) is None
    assert _call_read_veto(monkeypatch, {'macro_info': {'vix': {}}}) is None
    assert _call_read_veto(
        monkeypatch, {'macro_info': {'vix': {'current': None}}}) is None
    assert _call_read_veto(
        monkeypatch, {'macro_info': {'vix': {'current': 'n/a'}}}) is None
    assert _call_read_veto(
        monkeypatch, {'macro_info': {'vix': {'current': float('nan')}}}) is None


def test_read_veto_reproduces_the_2026_08_05_divergence(monkeypatch):
    """釘住事故情境：VIX 平靜（基本面側不觸發）但外資期貨重兵空單 → v4 紅燈。

    這正是「同一頁兩個相反結論」的成因。本測試不是要求兩邊一致（它們本來就不該
    一致），而是**證明分歧是可重現的常態**，因此揭露機制不可省略。
    """
    import pandas as pd

    _li = pd.DataFrame({
        '日期': ['8月4日', '8月5日'],
        '外資大小': [-24000.0, -25000.0],   # < -20,000 口 → v4 紅燈
        '選PCR': [95.0, 96.0],
    })
    _res = _call_read_veto(monkeypatch, {
        'macro_info': {'vix': {'current': 17.3}},   # < 20 → 基本面側完全不觸發
        'li_latest': _li,
    })
    assert _res is not None
    assert _res['status'].startswith('🔴'), \
        f'外資期貨 -25,000 口應觸發 v4 紅燈，實得 {_res["status"]}'
    assert _res['_vix'] == pytest.approx(17.3)
    assert _res['_futures'] == pytest.approx(-25000.0)


def test_read_veto_actually_uses_real_vix(monkeypatch):
    """VIX 必須真的接進去：VIX=26（>25）在期貨為 0 口時就該紅燈。

    v19.170 P0-2 的原始 bug 是硬編碼 `vix=15`，導致 VIX 兩條規則永久失效、
    紅黃燈只能靠期貨觸發。抽成函式後這條回歸守門要留著。
    """
    import pandas as pd

    _li = pd.DataFrame({'日期': ['8月5日'], '外資大小': [0.0], '選PCR': [100.0]})
    _red = _call_read_veto(monkeypatch, {
        'macro_info': {'vix': {'current': 26.0}}, 'li_latest': _li})
    assert _red is not None and _red['status'].startswith('🔴')

    _green = _call_read_veto(monkeypatch, {
        'macro_info': {'vix': {'current': 12.0}}, 'li_latest': _li})
    assert _green is not None and _green['status'].startswith('🟢')


# ══════════════════════════════════════════════════════════════════
# B. 修正二 — 韭菜指數門檻 SSOT 化（行為凍結）
# ══════════════════════════════════════════════════════════════════
# 現行線上行為的黃金值。**改這裡 = 改線上訊號**，必須是 user 明確核准的行為變更，
# 不可因為「看起來應該統一」而順手調整（§-1：沒需求不要動）。
_LEEK_GOLDEN = {
    'LEEK_ALERT_HIGH_PCT': 30.0,
    'LEEK_ALERT_LOW_PCT': -30.0,
    'LEEK_SCORE_HIGH_PCT': 10.0,
    'LEEK_SCORE_LOW_PCT': -5.0,
    'LEEK_PIVOT_HIGH_PCT': 20.0,
    'LEEK_PIVOT_LOW_PCT': -20.0,
}


def test_leek_thresholds_exist_and_values_frozen():
    """六個門檻常數存在且值未被更動（SSOT 化不得夾帶行為變更）。"""
    import src.config.config as _cfg
    for _name, _expected in _LEEK_GOLDEN.items():
        assert hasattr(_cfg, _name), f'缺少韭菜門檻常數 {_name}'
        assert getattr(_cfg, _name) == pytest.approx(_expected), (
            f'{_name} 從 {_expected} 被改成 {getattr(_cfg, _name)} —— '
            '這是**行為變更**（會改變線上訊號），須 user 核准後才可改本測試。'
        )


def test_leek_threshold_names_encode_their_purpose():
    """常數名必須帶用途前綴 + 單位後綴（§3.3 / §4.1）。

    `ALERT`／`SCORE`／`PIVOT` 讓「同數字不同義」不會被誤合併；
    `_PCT` 讓它不會被拿去比對 0~100 的融資標準化指數。
    """
    for _name in _LEEK_GOLDEN:
        assert _name.endswith('_PCT'), f'{_name} 缺單位後綴 _PCT'
        assert any(_name.startswith(f'LEEK_{_p}_')
                   for _p in ('ALERT', 'SCORE', 'PIVOT')), \
            f'{_name} 缺用途前綴（ALERT/SCORE/PIVOT）'


def test_margin_scale_leek_constants_are_kept_but_not_wired():
    """0~100 的融資標準化指數門檻（35/10）保留原值，且**不得**被兩個 section 引用。

    它們不是「還沒接線的同一套門檻」，而是**另一個指標**的門檻：
      - 35/10 屬融資餘額 5Y 標準化指數，值域 [0,100]、中位 50；
      - 畫面上跑的是小台法人空多比，值域約 [-100,+100]、中位 0。
    誰把它們 import 進 `section_chips` / `section_state` 拿去比對法人空多比，
    就是 §4.1 量綱錯誤（等於拿指數比比值）。
    """
    import src.config.config as _cfg
    assert _cfg.LEEK_HIGH_THRESHOLD == pytest.approx(35.0)
    assert _cfg.LEEK_LOW_THRESHOLD == pytest.approx(10.0)

    for _p in (_SECTION_CHIPS, _SECTION_STATE):
        _n = _names(_p)
        assert 'LEEK_HIGH_THRESHOLD' not in _n and 'LEEK_LOW_THRESHOLD' not in _n, (
            f'{_p.name} 引用了融資標準化指數的門檻（0~100）去比對法人空多比（±%）'
            ' —— §4.1 量綱錯誤。'
        )


@pytest.mark.parametrize('path', [_SECTION_CHIPS, _SECTION_STATE],
                         ids=['section_chips', 'section_state'])
def test_no_inline_leek_thresholds(path: Path):
    """韭菜門檻不得再 inline：任何 `_leek* <比較> 數字` 都算違憲（§3.3）。

    用 AST 而非 regex —— regex 擋不住 `30 < _leek` 這種左右對調的寫法，
    而那與 `_leek > 30` 完全等價。`_leek is not None` 不受影響（比較對象非數值）。
    """
    _violations: list[str] = []
    for _node in ast.walk(_tree(path)):
        if not isinstance(_node, ast.Compare):
            continue
        _operands = [_node.left, *_node.comparators]
        _has_leek = any(isinstance(_o, ast.Name) and 'leek' in _o.id.lower()
                        for _o in _operands)
        if not _has_leek:
            continue
        for _o in _operands:
            _num = _numeric(_o)
            if _num is not None:
                _violations.append(f'{path.name}:{_node.lineno}: 韭菜門檻 inline {_num:g}')
    assert not _violations, (
        '發現 inline 韭菜門檻（§3.3 禁止 magic number）：\n'
        + '\n'.join(_violations)
        + '\n\n請改用 src/config/config.py 的 LEEK_ALERT_* / LEEK_SCORE_* / '
          'LEEK_PIVOT_*（三組**刻意分名**，不可合併成同一個常數）。'
    )


@pytest.mark.parametrize(
    'path,expected',
    [(_SECTION_CHIPS, ('LEEK_ALERT_HIGH_PCT', 'LEEK_ALERT_LOW_PCT',
                       'LEEK_SCORE_HIGH_PCT', 'LEEK_SCORE_LOW_PCT')),
     (_SECTION_STATE, ('LEEK_PIVOT_HIGH_PCT', 'LEEK_PIVOT_LOW_PCT'))],
    ids=['section_chips', 'section_state'])
def test_sections_actually_import_their_leek_ssot(path: Path, expected: tuple):
    """反向驗證：門檻真的是從 SSOT 取的，不是整段判定被刪掉才「沒有 inline」。

    沒有這條，`test_no_inline_leek_thresholds` 會在「有人把韭菜訊號整段砍掉」時
    變成假綠燈。
    """
    _n = _names(path)
    _missing = [_c for _c in expected if _c not in _n]
    assert not _missing, f'{path.name} 未引用韭菜門檻 SSOT：{_missing}'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
