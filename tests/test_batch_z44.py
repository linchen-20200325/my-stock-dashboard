"""批 Z44 —— 客戶裁示 Q3＝B（逐字）：「統一改成既有核准語句：『外資買賣超未取得，本卡不下籌碼結論』。
只做最小文字與對應測試修改。不改版面、顏色、計算或投資結論。」（基底 origin/main `f96b5e1d`）

改動：L5 `section_chips.py` §三 籌碼卡 `_fn3 is None` 分支（外資列不存在＝F1，或外資列存在但
buy／sell 缺／未觀測＝F2）的 `_hye_concl` 一行文字：
  「三大法人資料缺「外資」欄位，本卡不下籌碼結論」→「外資買賣超未取得，本卡不下籌碼結論」。
同分支 `_hye_c`（TRAFFIC_NEUTRAL）、`_hye_ind`（「外資買賣超 ⬜ 未取得」）、`_hye_act` 與其他分支 ⛔ 不動。

本檔驗：
  A. F1（有投信、無外資 key）／F1'（BFI82U 缺外資列、'--'）／F2（外資 key 在但未觀測）→ 卡片結論為新句、
     顏色 TRAFFIC_NEUTRAL、指標列「外資買賣超 ⬜ 未取得」（以真 `strategy_conclusion` 整段 HTML 逐字比對）。
  B. 整段 §三 輸出 ＝ 修前（本批還原體）輸出只把舊句換成新句 —— 版面／顏色／其他文字逐字不變。
  C. 突變：新句改回舊句（＝ 本批還原體）→ A 轉紅。
  D. 觀測值（外資 key 有真值）輸出與修前逐字相同（本批不碰）。
舊批次（Z33／Z35／Z36）「還原為基底檔」的還原鏈串接本批 pair（同 Z33 串 Z34 慣例；⛔ 不動各批 pair 本身）。
"""
from __future__ import annotations

import functools
import importlib.util
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]

# ══════════════════════════════════════════════════════════════════════════
# 0. 還原 pair（先於任何 tests.* import 定義 —— 舊批次測試檔會回頭 import 本表，避免循環 import 半初始化）
# ══════════════════════════════════════════════════════════════════════════
_CHIPS = 'src/ui/tabs/macro/section_chips.py'
Z44_NEW = '外資買賣超未取得，本卡不下籌碼結論'
Z44_OLD = '三大法人資料缺「外資」欄位，本卡不下籌碼結論'

#: (修後逐字, 修前逐字) —— 正式碼字面一改即找不到替換點而失敗（字面錨點）
Z44_CHIPS_PAIR = (
    f"            _hye_concl = '{Z44_NEW}'\n",
    f"            _hye_concl = '{Z44_OLD}'\n",
)
Z44_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {_CHIPS: (Z44_CHIPS_PAIR,)}


def z44_revert_for(file_path, code: str) -> str:
    """舊批次還原鏈串接用：給模組 `__file__`（或 repo 相對路徑）與原始碼，換回本批之前的寫法（無 pair 則原樣）。"""
    p = pathlib.Path(file_path)
    rel = (p.resolve().relative_to(_ROOT) if p.is_absolute() else p).as_posix()
    for new, old in Z44_REVERT_PAIRS.get(rel, ()):
        assert code.count(new) == 1, f'{rel} 替換點不唯一或已不存在：{new!r}'
        code = code.replace(new, old)
    return code


@functools.lru_cache(maxsize=None)
def z44_pre_chips_module():
    """現行 section_chips 只把本批改動換回修前寫法（獨立模組物件，不影響本尊）。"""
    path = _ROOT / _CHIPS
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader('_z44_pre_chips', loader=None))
    m.__file__ = str(path)
    exec(compile(z44_revert_for(_CHIPS, path.read_text(encoding='utf-8')), str(path), 'exec'), m.__dict__)
    return m


# ══════════════════════════════════════════════════════════════════════════
# 以下才 import 專案與舊批次測試
# ══════════════════════════════════════════════════════════════════════════
import pytest  # noqa: E402

import src.ui.tabs.macro.section_chips as SC  # noqa: E402
from shared.colors import TRAFFIC_NEUTRAL  # noqa: E402
from src.ui.render.ui_widgets import STRATEGY_TECHNICAL, strategy_conclusion  # noqa: E402
from tests import test_batch_z33_inst as Z33  # noqa: E402

_IND = '外資買賣超 ⬜ 未取得'


def _cases():
    """F1：有投信、無外資 key；F1'：BFI82U 缺外資列／'--'（key 在、未觀測）；F2：FinMind 補零推出（未觀測）。"""
    return {
        'f1_no_foreign_key': Z33.MISSING_KEY['no_foreign_key'],
        **{k: v for k, v in Z33.UNOBSERVED.items()},
    }


_CASE_IDS = ('f1_no_foreign_key', 'f1_missing_row', 'f1_dashdash', 'f2_buy_nan_sell_300', 'f2_sell_nan_buy_500')


def _md(out) -> list[str]:
    return [t for k, t in out if k == 'markdown']


def _assert_card(mod, inst, mp):
    out = Z33._run_chips(mod, inst, mp)
    card = strategy_conclusion(STRATEGY_TECHNICAL, _IND, Z44_NEW, color=TRAFFIC_NEUTRAL)
    assert card in _md(out)                                   # 指標列＋新句＋灰色，整段 HTML 逐字
    assert not any(Z44_OLD in t for _k, t in out)             # 舊句不再出現
    return out


def test_fixture_ids_cover_documented_cases():
    assert set(_cases()) == set(_CASE_IDS)
    assert '外資及陸資' not in _cases()['f1_no_foreign_key']() and '投信' in _cases()['f1_no_foreign_key']()


@pytest.mark.parametrize('case', _CASE_IDS)
def test_card_uses_approved_sentence_neutral_color(case, monkeypatch):
    """A. F1／F2：結論＝客戶核准語句、顏色 TRAFFIC_NEUTRAL、指標列「外資買賣超 ⬜ 未取得」。"""
    _assert_card(SC, _cases()[case](), monkeypatch)


@pytest.mark.parametrize('case', _CASE_IDS)
def test_only_the_sentence_changed(case, monkeypatch):
    """B. 整段 §三 輸出 ＝ 修前輸出只把舊句換新句（版面、顏色、行動建議、柱狀圖逐字不變）。"""
    now = Z33._run_chips(SC, _cases()[case](), monkeypatch)
    pre = Z33._run_chips(z44_pre_chips_module(), _cases()[case](), monkeypatch)
    assert now != pre
    assert now == [(k, t.replace(Z44_OLD, Z44_NEW)) for k, t in pre]


@pytest.mark.parametrize('case', _CASE_IDS)
def test_mutant_old_sentence_turns_red(case, monkeypatch):
    """C. 突變：新句改回舊句（本批還原體）→ A 必須轉紅。"""
    with pytest.raises(AssertionError):
        _assert_card(z44_pre_chips_module(), _cases()[case](), monkeypatch)


@pytest.mark.parametrize('case', sorted(Z33.OBSERVED))
def test_observed_identical_to_pre(case, monkeypatch):
    """D. 外資有觀測值 ⇒ 不走本分支，輸出與修前逐字相同。"""
    now = Z33._run_chips(SC, Z33.OBSERVED[case](), monkeypatch)
    pre = Z33._run_chips(z44_pre_chips_module(), Z33.OBSERVED[case](), monkeypatch)
    assert now == pre
    assert not any(Z44_NEW in t or Z44_OLD in t for _k, t in now)


def test_source_anchor_exactly_once():
    src = (_ROOT / _CHIPS).read_text(encoding='utf-8')
    assert src.count(Z44_CHIPS_PAIR[0]) == 1 and Z44_OLD not in src
