"""tests/test_nav1_ia_nav4.py — NAV-1 L0 `shared/ia_nav4.py` 守衛（fast lane；純函式，不跑 Streamlit）。

守什麼：
  1. 四頁標籤**逐字**是客戶指定的那四個（含 emoji、空格、順序）—— 期望值寫死在本檔當第二來源，不從被測檔讀出來自己比自己。
  2. `PAGE4_TO_VIEW` 完整：每個 view 頁恰在四頁之一或 legacy-only，一頁不漏、不重；🎯 標的＝找標的＋查一檔。
  3. `reconcile_nav4` 真的會炸（合成壞資料逐項餵，證明它不是空殼）。
  4. `resolve_legacy_flag` 的真值表（尤其：空值／亂值**不得**把人丟進 legacy）。
  5. L0 純度：import 它不會帶進 streamlit；它沒有 I/O。
  6. key 名稱只存在於允許的檔案（不撞既有 widget）。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import textwrap

import pytest

from shared import ia_nav, ia_nav4

_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: 客戶 DEC-097＋2026-10-28 指示逐字（第二來源）。順序＝導覽順序。
_CLIENT_LABELS = ("📊 市場", "🎯 標的", "💼 持股", "👤 我的")


class TestLabels:
    def test_labels_are_the_clients_four_verbatim_in_order(self):
        assert tuple(ia_nav4.PAGE4_LABELS.values()) == _CLIENT_LABELS
        assert ia_nav4.page4_options() == _CLIENT_LABELS

    def test_exactly_four_pages(self):
        assert len(ia_nav4.PAGE4_LABELS) == 4
        assert ia_nav4.page4_ids() == (
            ia_nav4.P4_MARKET, ia_nav4.P4_TARGET, ia_nav4.P4_HOLD, ia_nav4.P4_ME)

    def test_labels_fit_one_line(self):
        for _l in ia_nav4.PAGE4_LABELS.values():
            assert 0 < len(_l) <= ia_nav4._LABEL_MAX_CHARS

    def test_pages_ids_do_not_collide_with_ia_nav_view_ids(self):
        assert not set(ia_nav4.PAGE4_LABELS) & set(ia_nav.PAGE_LABELS)

    def test_default_is_market(self):
        assert ia_nav4.default_page4() == ia_nav4.P4_MARKET

    def test_unknown_label_and_id_fail_loud(self):
        with pytest.raises(ValueError):
            ia_nav4.page4_from_label("📊 大盤")      # D2 舊名不是四頁導覽的選項
        with pytest.raises(ValueError):
            ia_nav4.page4_label("market")             # view id 不是主導覽 id
        with pytest.raises(ValueError):
            ia_nav4.coerce_page4("market")
        for _bad in (123, "", ["x"], {"a": 1}, 1.5):      # 不可雜湊型別也要是 ValueError，不是 TypeError
            with pytest.raises(ValueError):
                ia_nav4.coerce_page4(_bad)
        for _bad in (["x"], 5, ""):
            with pytest.raises(ValueError):
                ia_nav4.resolve_view(ia_nav4.P4_TARGET, _bad)
        assert ia_nav4.coerce_page4(None) == ia_nav4.P4_MARKET

    def test_label_roundtrip(self):
        for _p, _l in ia_nav4.PAGE4_LABELS.items():
            assert ia_nav4.page4_from_label(_l) == _p
            assert ia_nav4.page4_label(_p) == _l


class TestMapping:
    #: 第二來源：寫死的期望對映（view id 字面值即 `ia_nav` 現行常數值）。
    _EXPECT = {
        "p4_market": ("market",),
        "p4_target": ("find", "inspect"),
        "p4_hold": ("hold",),
        "p4_me": ("me",),
    }

    def test_mapping_is_exactly_the_expected_one(self):
        assert dict(ia_nav4.PAGE4_TO_VIEW) == self._EXPECT

    def test_every_ia_nav_view_is_in_exactly_one_place(self):
        _flat = [v for vs in ia_nav4.PAGE4_TO_VIEW.values() for v in vs] + list(ia_nav4.LEGACY_ONLY_VIEWS)
        assert sorted(_flat) == sorted(ia_nav.PAGE_LABELS)
        assert len(_flat) == len(set(_flat))

    def test_legacy_only_views_are_today_and_why(self):
        assert set(ia_nav4.LEGACY_ONLY_VIEWS) == {"today", "why"}

    def test_target_has_two_leaves_built_from_ia_nav_labels(self):
        assert ia_nav4.has_leaves(ia_nav4.P4_TARGET)
        assert ia_nav4.leaf_options(ia_nav4.P4_TARGET) == (
            ia_nav.page_label("find"), ia_nav.page_label("inspect"))
        for _p in (ia_nav4.P4_MARKET, ia_nav4.P4_HOLD, ia_nav4.P4_ME):
            assert not ia_nav4.has_leaves(_p)

    def test_resolve_view(self):
        assert ia_nav4.resolve_view(ia_nav4.P4_MARKET) == "market"
        assert ia_nav4.resolve_view(ia_nav4.P4_MARKET, "inspect") == "market"   # 單頁忽略葉
        assert ia_nav4.resolve_view(ia_nav4.P4_TARGET) == "find"                # 預設第一葉
        assert ia_nav4.resolve_view(ia_nav4.P4_TARGET, "inspect") == "inspect"
        with pytest.raises(ValueError):
            ia_nav4.resolve_view(ia_nav4.P4_TARGET, "hold")                     # 不靜默退回預設葉

    def test_leaf_from_label(self):
        _lab = ia_nav.page_label("inspect")
        assert ia_nav4.leaf_from_label(ia_nav4.P4_TARGET, _lab) == "inspect"
        with pytest.raises(ValueError):
            ia_nav4.leaf_from_label(ia_nav4.P4_TARGET, "💼 我的持股")


class TestReconcileHasTeeth:
    """`reconcile_nav4` 不是空殼：每一種漂移都要 RuntimeError（用 monkeypatch 合成壞資料）。"""

    def test_clean_state_passes_with_the_real_dispatch_ids(self):
        ia_nav4.reconcile_nav4(set(ia_nav.PAGE_LABELS))
        ia_nav4.reconcile_nav4()

    def test_missing_view_in_dispatch_table(self):
        with pytest.raises(RuntimeError):
            ia_nav4.reconcile_nav4(set(ia_nav.PAGE_LABELS) - {"hold"})

    def test_extra_view_in_dispatch_table(self):
        with pytest.raises(RuntimeError):
            ia_nav4.reconcile_nav4(set(ia_nav.PAGE_LABELS) | {"ghost"})

    def test_five_pages(self, monkeypatch):
        _l = dict(ia_nav4.PAGE4_LABELS)
        _l["p4_extra"] = "⚡ 行動"
        monkeypatch.setattr(ia_nav4, "PAGE4_LABELS", _l)
        with pytest.raises(RuntimeError, match="4 頁"):
            ia_nav4.reconcile_nav4()

    def test_mapping_key_drift(self, monkeypatch):
        _m = dict(ia_nav4.PAGE4_TO_VIEW)
        _m.pop("p4_me")
        monkeypatch.setattr(ia_nav4, "PAGE4_TO_VIEW", _m)
        with pytest.raises(RuntimeError):
            ia_nav4.reconcile_nav4()

    def test_view_mapped_twice(self, monkeypatch):
        _m = dict(ia_nav4.PAGE4_TO_VIEW)
        _m["p4_hold"] = ("hold", "market")
        monkeypatch.setattr(ia_nav4, "PAGE4_TO_VIEW", _m)
        with pytest.raises(RuntimeError, match="多個位置"):
            ia_nav4.reconcile_nav4()

    def test_view_dropped(self, monkeypatch):
        _m = dict(ia_nav4.PAGE4_TO_VIEW)
        _m["p4_target"] = ("find",)
        monkeypatch.setattr(ia_nav4, "PAGE4_TO_VIEW", _m)
        with pytest.raises(RuntimeError, match="漏接"):
            ia_nav4.reconcile_nav4()

    def test_legacy_only_overlaps_a_page(self, monkeypatch):
        monkeypatch.setattr(ia_nav4, "LEGACY_ONLY_VIEWS", ("today", "why", "market"))
        with pytest.raises(RuntimeError):
            ia_nav4.reconcile_nav4()

    def test_label_too_long_or_duplicated(self, monkeypatch):
        _l = dict(ia_nav4.PAGE4_LABELS)
        _l["p4_hold"] = "💼 我的持股戰情室"
        monkeypatch.setattr(ia_nav4, "PAGE4_LABELS", _l)
        with pytest.raises(RuntimeError, match="單行"):
            ia_nav4.reconcile_nav4()
        _l2 = dict(ia_nav4.PAGE4_LABELS)
        _l2["p4_hold"] = _l2["p4_market"]
        monkeypatch.setattr(ia_nav4, "PAGE4_LABELS", _l2)
        with pytest.raises(RuntimeError, match="不重複"):
            ia_nav4.reconcile_nav4()

    def test_reconcile_uses_raise_not_assert(self):
        _src = (_ROOT / "shared" / "ia_nav4.py").read_text(encoding="utf-8")
        assert "assert " not in _src.split("def reconcile_nav4")[1], (
            "對帳改成 assert 了 —— `python -O` 會整條拿掉")


class TestLegacyFlag:
    @pytest.mark.parametrize("qv,cur,expect", [
        ("1", False, True),
        ("1", True, True),
        ("0", True, False),
        ("0", False, False),
        (" 1 ", False, True),
        (None, False, False),
        (None, True, True),         # 沒帶參數 ⇒ 維持旗標（耐 rerun / OAuth callback 清掉網址）
        ("", False, False),         # 空值不得把一般使用者丟進 legacy
        ("", True, True),
        ("yes", False, False),
        ("true", False, False),
        ("2", False, False),
        (["1"], False, False),      # 非字串（亂型別）⇒ 維持
        (1, False, False),
    ])
    def test_truth_table(self, qv, cur, expect):
        assert ia_nav4.resolve_legacy_flag(qv, cur) is expect

    def test_param_and_session_names(self):
        assert ia_nav4.LEGACY_QUERY_PARAM == "legacy"
        assert ia_nav4.LEGACY_SESSION_KEY == "_nav4_legacy"


class TestPurity:
    def test_import_does_not_pull_streamlit(self):
        _code = textwrap.dedent(f"""
            import sys; sys.path.insert(0, {str(_ROOT)!r})
            import shared.ia_nav4
            assert 'streamlit' not in sys.modules, 'ia_nav4 把 streamlit 拉進來了'
            print('PURE_OK')
        """)
        r = subprocess.run([sys.executable, "-I", "-c", _code], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "PURE_OK" in r.stdout, r.stderr[-1500:]

    def test_no_io_imports(self):
        import ast
        _t = ast.parse((_ROOT / "shared" / "ia_nav4.py").read_text(encoding="utf-8"))
        _mods = set()
        for n in ast.walk(_t):
            if isinstance(n, ast.Import):
                _mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                _mods.add((n.module or "").split(".")[0])
        assert _mods <= {"__future__", "collections", "shared"}, _mods


class TestKeyNames:
    def test_keys_only_defined_in_the_allowed_files(self):
        """`_nav4_` 前綴的 key 只准出現在 L0 常數檔、元件檔、app.py（旗標）與本批測試（不撞既有 widget）。"""
        _allowed = {
            "shared/ia_nav4.py", "src/ui/views/shell_nav4.py", "app.py",
            # QA 回修：三個 view 的頁內文字分流以註解／常數名引用旗標值 `_nav4_legacy`（字面值，不 import ia_nav4）；
            # 相等由 tests/test_nav1_default_mode_text.py 釘住。
            "src/ui/views/page_me.py", "src/ui/views/page_market.py", "src/ui/views/page_hold.py",
        }
        _hits = []
        for _base in ("src", "shared", "infra", "scripts"):
            for p in sorted((_ROOT / _base).rglob("*.py")):
                if "_nav4_" in p.read_text(encoding="utf-8"):
                    _hits.append(str(p.relative_to(_ROOT)))
        _hits_app = "_nav4_" in (_ROOT / "app.py").read_text(encoding="utf-8")
        if _hits_app:
            _hits.append("app.py")
        assert set(_hits) <= _allowed, f"`_nav4_` 出現在允許清單之外：{sorted(set(_hits) - _allowed)}"

    def test_all_state_keys_share_the_prefix_and_are_distinct(self):
        _keys = [ia_nav4.NAV4_PAGE_KEY, ia_nav4.NAV4_TARGET_LEAF_KEY, ia_nav4.NAV4_WIDGET_SIDE_KEY,
                 ia_nav4.NAV4_WIDGET_BOTTOM_KEY, ia_nav4.NAV4_WIDGET_LEAF_KEY, ia_nav4.LEGACY_SESSION_KEY]
        assert all(k.startswith("_nav4_") for k in _keys)
        assert len(set(_keys)) == len(_keys)
        assert ia_nav4.NAV4_BOTTOM_CONTAINER_KEY == "nav4_bottom"
