"""批 Z42：板塊資金「未取得」說明移除未核准的「（缺 N 日）」片段（第 26 次自檢 B 組 K1）。

背景
----
- 批 Z39 新增的 L0 `shared/sector_flow_thresholds.py::format_unavailable_caption` 產出
  「⬜ 未取得：A（缺 3 日）、B（缺 20 日）」。前綴「⬜ 未取得：」沿用既有核准字樣
  （`section_chips`；Q-z26 核准「未取得」），板塊名是資料；但「（缺 {n} 日）」**沒有客戶核准出處**
  （Q-z26 只核准「未取得」、Q-z28 只核准「目前僅含上市資料」）。
- 規則：未經客戶核准不得新增可見字句 → 內部自修＝移除該片段，只列板塊名：「⬜ 未取得：A、B」。
- `n_missing_days` 資料欄位（L2 計算、metadata）保留不動，只是不顯示。

突變：`Z42_REVERT_PAIRS` 為「修後逐字 → 修前（基底 `9c09df3e`）逐字」，每組在現行檔恰出現一次；
還原體 sha256 ＝ 基底實檔（`git show 9c09df3e:shared/sector_flow_thresholds.py | sha256sum`）。
把舊 f-string 行換回去 → 本檔輸出斷言必須轉紅。
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys

import pytest

from shared.sector_flow_thresholds import (
    SECTOR_FLOW_UNAVAILABLE_PREFIX,
    format_unavailable_caption,
)

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_L0 = "shared/sector_flow_thresholds.py"

#: 還原 pair 之一：舊 f-string 行（顯示「（缺 N 日）」）。
_Z42_CODE_PAIR: tuple[str, str] = (
    '        _items.append(str(r.get("sector")))\n',
    '        _n = r.get("n_missing_days")\n'
    '        _items.append(f"{r.get(\'sector\')}（缺 {_n} 日）" if _n is not None\n'
    '                      else str(r.get("sector")))\n',
)
#: 還原 pair 之二：docstring（僅為讓還原體逐字 ＝ 基底，sha 自證）。
_Z42_DOC_PAIR: tuple[str, str] = (
    '    """「⬜ 未取得：A、B」;沒有未取得板塊 → None(L5 不畫 caption)。\n'
    '\n'
    '    批 Z39:兩個 UI 消費點(`tab_sector_flow` / v2 `page_find`)共用同一份格式(純函式、零 I/O)。\n'
    '    只列 `unavailable` 為 True 的板塊;交易日不足(insufficient)\n'
    '    的板塊另有既有「🕓 資料不足」說明,不在此重複。\n'
    '    批 Z42:只輸出核准前綴＋板塊名(以「、」串接)。原「（缺 N 日）」片段無客戶核准出處 → 移除;\n'
    '    `n_missing_days` 資料欄位仍由 L2 計算並保留於 metadata,只是不顯示。\n'
    '    """\n',
    '    """「⬜ 未取得：A（缺 3 日）、B（缺 20 日）」;沒有未取得板塊 → None(L5 不畫 caption)。\n'
    '\n'
    '    批 Z39:兩個 UI 消費點(`tab_sector_flow` / v2 `page_find`)共用同一份格式(純函式、零 I/O)。\n'
    '    只列 `unavailable` 為 True 的板塊(`n_missing_days` 由 L2 計);交易日不足(insufficient)\n'
    '    的板塊另有既有「🕓 資料不足」說明,不在此重複。\n'
    '    """\n',
)
Z42_REVERT_PAIRS: dict[str, tuple[tuple[str, str], ...]] = {
    _L0: (_Z42_DOC_PAIR, _Z42_CODE_PAIR),
}
#: 基底 `9c09df3e` 原始檔 sha256（`git show 9c09df3e:shared/sector_flow_thresholds.py | sha256sum` 實算）。
Z42_BASE_SHA = {
    _L0: "6adad7aeb329918610bffce51d0df8c41c7aeddeb0c89463f193e938fe18a438",
}

_MUT_SEQ = [0]


def z42_revert(rel: str, code: str, pairs=None) -> str:
    for new, old in (Z42_REVERT_PAIRS[rel] if pairs is None else pairs):
        assert code.count(new) == 1, f"{rel} 替換點不唯一或已不存在：{new!r}"
        code = code.replace(new, old)
    return code


def _mutant(rel: str, pairs):
    """現行檔逐字置換 `pairs`（修後 → 修前）後，在獨立模組物件中執行（不影響本尊）。"""
    path = _ROOT / rel
    code = z42_revert(rel, path.read_text(encoding="utf-8"), pairs)
    _MUT_SEQ[0] += 1
    name = f"_z42_mut_{_MUT_SEQ[0]}"
    m = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    m.__file__ = str(path)
    sys.modules[name] = m
    exec(compile(code, str(path), "exec"), m.__dict__)
    return m


_SECTORS = [
    {"sector": "好", "unavailable": False, "insufficient": False, "n_missing_days": 0},
    {"sector": "上櫃光電", "unavailable": True, "insufficient": False, "n_missing_days": 3},
    {"sector": "上櫃生技", "unavailable": True, "insufficient": False, "n_missing_days": 20},
    {"sector": "短窗", "unavailable": True, "insufficient": True, "n_missing_days": 5},
    {"sector": "無計數", "unavailable": True, "insufficient": False},
]
_EXPECTED = "⬜ 未取得：上櫃光電、上櫃生技、無計數"


def _assert_only_approved(fmt) -> None:
    """輸出只含核准前綴＋板塊名（以「、」串接），不含「缺…日」任何組合。"""
    out = fmt(_SECTORS)
    assert out == _EXPECTED
    assert out.startswith(SECTOR_FLOW_UNAVAILABLE_PREFIX)
    assert SECTOR_FLOW_UNAVAILABLE_PREFIX == "⬜ 未取得："
    body = out[len(SECTOR_FLOW_UNAVAILABLE_PREFIX):]
    assert body.split("、") == ["上櫃光電", "上櫃生技", "無計數"]
    assert "缺" not in out and "日" not in out
    for n in (3, 20):
        assert f"缺 {n} 日" not in out and f"（缺 {n} 日）" not in out


class TestApprovedTextOnly:
    def test_output_prefix_plus_names_only(self):
        _assert_only_approved(format_unavailable_caption)

    def test_single_sector(self):
        assert format_unavailable_caption([_SECTORS[1]]) == "⬜ 未取得：上櫃光電"

    def test_none_behaviour_unchanged(self):
        assert format_unavailable_caption([]) is None
        assert format_unavailable_caption(None) is None
        assert format_unavailable_caption(_SECTORS[:1]) is None          # 無未取得
        assert format_unavailable_caption([_SECTORS[3]]) is None         # insufficient 排除
        assert format_unavailable_caption(["非 mapping", 1]) is None      # 非 mapping 略過

    def test_order_preserved_no_dedupe_change(self):
        """排序／去重行為照舊（修前即依輸入順序、不去重）。"""
        rows = [_SECTORS[2], _SECTORS[1], _SECTORS[2]]
        assert format_unavailable_caption(rows) == "⬜ 未取得：上櫃生技、上櫃光電、上櫃生技"

    def test_n_missing_days_input_untouched(self):
        rows = [dict(s) for s in _SECTORS]
        format_unavailable_caption(rows)
        assert rows == _SECTORS                                           # 純函式、不改輸入


class TestMutation:
    def test_reverted_source_equals_base_file(self):
        code = z42_revert(_L0, (_ROOT / _L0).read_text(encoding="utf-8"))
        assert hashlib.sha256(code.encode("utf-8")).hexdigest() == Z42_BASE_SHA[_L0]

    def test_pairs_each_unique_in_current_file(self):
        code = (_ROOT / _L0).read_text(encoding="utf-8")
        for new, _old in Z42_REVERT_PAIRS[_L0]:
            assert code.count(new) == 1

    def test_mutant_old_fstring_turns_red(self):
        """把舊 f-string 行換回 → 「缺 N 日」重現 → 核准字句斷言轉紅。"""
        M = _mutant(_L0, (_Z42_CODE_PAIR,))
        assert "（缺 3 日）" in M.format_unavailable_caption(_SECTORS)
        with pytest.raises(AssertionError):
            _assert_only_approved(M.format_unavailable_caption)

    def test_full_revert_turns_red(self):
        M = _mutant(_L0, Z42_REVERT_PAIRS[_L0])
        with pytest.raises(AssertionError):
            _assert_only_approved(M.format_unavailable_caption)
