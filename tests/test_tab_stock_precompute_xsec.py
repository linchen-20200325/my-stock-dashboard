"""v18.309 Bug2 Stage 1 — tab_stock._precompute_xsec 跨段依賴 compute-once 測試。

目的:Stage 2 物理重排前的安全基礎。本函式把「顯示段算、AI 摘要跨段引用」
的 4 組值一次算完,讓 AI 摘要與顯示段執行順序解耦。

涵蓋(重點 = graceful degradation,§1 不 raise / 不偽造):
1. 壞輸入(None / 空 df)→ 回 dict,不 raise
2. 缺資料的組別 → 該 key 缺席(AI 端 guard 落 fallback,行為等價)
3. 回傳型別 = dict
"""
from __future__ import annotations

import pandas as pd

import tab_stock


def test_returns_dict_on_none():
    """全 None 輸入 → 回 dict,不 raise(§1 Fail-safe)。"""
    r = tab_stock._precompute_xsec(None, None, None, None, None)
    assert isinstance(r, dict)


def test_returns_dict_on_empty():
    r = tab_stock._precompute_xsec(pd.DataFrame(), "2330", None, None, None)
    assert isinstance(r, dict)


def test_chip_keys_absent_when_no_data():
    """籌碼資料缺(空 df / 無三大法人欄)→ con20/cty20/sig20 應缺席(不偽造 0)。

    AI 摘要端 `try: _xsec["con20"]` 會 KeyError → except 落 fallback『未取得』,
    與 Stage 1 前(_con20 未定義 → NameError → 同 fallback)行為等價。
    """
    r = tab_stock._precompute_xsec(pd.DataFrame(), "2330", None, None, None)
    # 籌碼算不出 → 三個 key 要嘛全有要嘛全無;空 df 應全無
    has_chip = all(k in r for k in ("con20", "cty20", "sig20"))
    assert not has_chip, "空 df 不應偽造籌碼值"


def test_no_partial_chip_keys():
    """籌碼 3 key 原子性:不可只有部分(con20 有但 sig20 無)。"""
    r = tab_stock._precompute_xsec(pd.DataFrame(), "2330", None, None, None)
    chip_present = [k for k in ("con20", "cty20", "sig20") if k in r]
    assert chip_present in ([], ["con20", "cty20", "sig20"]), \
        f"籌碼 key 非原子:{chip_present}"


def test_helper_exists_and_callable():
    assert callable(getattr(tab_stock, "_precompute_xsec", None))


def test_render_reads_xsec_not_section_locals():
    """render_tab_stock AI 摘要必須改讀 _xsec(不再用 _con20/_li_green section local)。"""
    src = open(tab_stock.__file__, encoding="utf-8").read()
    # AI 摘要區段應引用 _xsec
    assert '_xsec["con20"]' in src or "_xsec['con20']" in src
    assert "_xsec.get('rs_val')" in src
    assert "_xsec.get('capital')" in src
    # 不應再有「AI 摘要直接讀 section local」的舊寫法(_conc_str2 用 _con20)
    assert "f'集中度={_con20" not in src, "AI 摘要仍直讀 section local _con20"
