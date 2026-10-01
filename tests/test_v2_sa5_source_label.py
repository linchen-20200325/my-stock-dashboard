"""批 SA5（B5-f1）：📖 憑什麼頁「值從哪來」對 `DangerSpec.source` 是**欄名錯** —— 那一欄實為**門檻出處**。

- 總經燈與參考走勢的 `source` 讀自 `shared/macro_buckets.py::DangerSpec.source`（L0 註解「門檻來源」）
  ⇒ 欄名「門檻出處」（沿用今天頁「▸ 詳細」同一欄位的既有字樣，⛔ 不是新字）。
- 持股燈的 `source` 讀自 `shared/station_specs.py`（L0 註解「這盞燈的值從哪來」）⇒ 原樣「值從哪來」。
"""
from __future__ import annotations

import inspect

import src.ui.views.page_today as T
import src.ui.views.page_why as P


def test_the_reused_label_already_exists_verbatim_on_the_today_page():
    """K1：「門檻出處」是既有字樣（今天頁標同一個 `DangerSpec.source`），不是新造的字。"""
    assert '("門檻出處", _spec.source)' in inspect.getsource(T)
    assert P.SOURCE_LABEL_THRESHOLD == "門檻出處"
    assert P.SOURCE_LABEL_VALUE == "值從哪來"


def test_source_label_by_family():
    assert P.source_label(P.FAMILY_MACRO) == "門檻出處"
    assert P.source_label(P.REFERENCE_FAMILY) == "門檻出處"
    assert P.source_label(P.FAMILY_HOLD) == "值從哪來"


def test_macro_table_says_threshold_source_and_hold_table_keeps_value_source():
    scan = P.load_specs()
    macro = [r for r in scan.rows if r.family == P.FAMILY_MACRO]
    hold = [r for r in scan.rows if r.family == P.FAMILY_HOLD]
    assert macro and hold
    for d, r in zip(P._spec_table_rows(macro), macro):
        assert "值從哪來" not in d and d["門檻出處"] == (r.source or "—"), d
    for d, r in zip(P._spec_table_rows(hold), hold):
        assert "門檻出處" not in d and d["值從哪來"] == (r.source or "—"), d


def test_reference_table_says_threshold_source():
    """參考走勢的 `source` 也是 `DangerSpec.source` ⇒「門檻出處」；欄位數仍是四欄、仍無「門檻」欄。"""
    scan = P.load_specs()
    refs = scan.reference_rows
    assert refs
    for d, r in zip(P._reference_table_rows(refs), refs):
        assert set(d) == {"這一條", "單位", "這條線在說什麼", "門檻出處"}, d
        assert d["門檻出處"] == (r.source or "—")


def test_spec_flag_card_source_label_follows_family():
    """規格標記卡：總經燈（`why.spec.margin`）→「門檻出處」；持股燈 → 仍「值從哪來」。

    以 L0 當下真實列各取一盞改成 degraded 來建卡（⛔ 不依賴當下 L0 剛好標記了哪一盞）。
    """
    import dataclasses
    scan = P.load_specs()
    for family, want, other in ((P.FAMILY_MACRO, "門檻出處", "值從哪來"),
                                (P.FAMILY_HOLD, "值從哪來", "門檻出處")):
        row = next(r for r in scan.rows if r.family == family and r.source)
        row = dataclasses.replace(row, wired=True, discriminative=False,
                                  degraded_reason="一段 L0 寫的原因")
        facts = dict(P.build_spec_flag_card(row)[1])
        assert facts.get(want) == row.source, (family, facts)
        assert other not in facts, (family, facts)


def test_live_margin_flag_card_says_threshold_source():
    built = [b for b in P.build_spec_flag_cards(P.load_specs()) if b[0].key == "why.spec.margin"]
    assert built, "L0 目前沒有標記融資那一盞 —— 這一條沒有東西可驗"
    facts = dict(built[0][1])
    assert facts.get("門檻出處", "").startswith("SSOT:MARGIN_BALANCE_OVERHEAT"), facts
    assert "值從哪來" not in facts
