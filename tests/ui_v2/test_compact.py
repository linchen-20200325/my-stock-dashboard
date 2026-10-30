"""Phase 3 步驟 1：`src/ui_v2/compact.py` 守衛。

規格：`docs/vnext/PHASE3_SHARED_COMPONENTS_WIREFRAME_2026-10-30.md` §3／§5；
Migration Plan §16.2 步驟 1；客戶裁示 DEC-115。
"""
from __future__ import annotations

import ast
import hashlib
import math
import re
from pathlib import Path

import pytest

from shared import ui_state as us
from src.ui_v2 import compact as cp
from src.ui_v2 import components, markup, tokens

ROOT = Path(__file__).resolve().parents[2]
COMPACT_PY = ROOT / "src" / "ui_v2" / "compact.py"
CONTRACT = ROOT / "docs" / "vnext" / "PRESENTATION_CONTRACT_vNext_2026-10-29.md"
NAN = float("nan")


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


# ══════════════════════════════════════════════════════════════════
# 既有輸出 byte-identical
# ══════════════════════════════════════════════════════════════════
class TestExistingUntouched:
    def test_page_css_sha256_unchanged(self):
        # 線框 §2.5 基準
        assert len(markup.page_css("dark")) == 6391
        assert len(markup.page_css("light")) == 6391
        assert _sha(markup.page_css("dark")) == "432d88ab064e5144"
        assert _sha(markup.page_css("light")) == "2ad61fd99eea422c"

    def test_tokens_existing_mapping_unchanged(self):
        assert len(tokens.DARK) == len(tokens.LIGHT) == 30
        assert _sha(repr(sorted(tokens.DARK.items()))) == "27d0fd646941f9bc"
        assert _sha(repr(sorted(tokens.LIGHT.items()))) == "882f36a2ea4f4b2d"
        assert _sha(repr(sorted(tokens.SPACING.items()))) == "89559023a13a69d9"

    def test_geometry_tokens_additive_and_separate(self):
        geo = tokens.COMPACT_GEOMETRY
        assert geo["--cp-chip-radius"] == "999px"
        assert geo["--cp-card-radius-bp"] == "14px"
        assert geo["--cp-slot-h-desktop"] == "220px" and geo["--cp-slot-h-mobile"] == "140px"
        assert geo["--cp-mini-h"] == "96px" and geo["--cp-spark-h"] == "64px"
        assert geo["--cp-touch-min"] == "44px"
        # 不得混進 dark/light（否則 page_css 的 :root 會變）
        assert not (set(geo) & set(tokens.DARK)) and not (set(geo) & set(tokens.LIGHT))
        # 14px 只新增、不套用
        assert "var(--cp-card-radius-bp)" not in cp.compact_css()

    def test_badges_still_eleven(self):
        assert len(components.BADGES) == 11


# ══════════════════════════════════════════════════════════════════
# AST／邊界守衛（M8、M10）
# ══════════════════════════════════════════════════════════════════
class TestBoundaries:
    ALLOWED_ROOTS = {"__future__", "math", "numbers", "re", "unicodedata", "dataclasses", "html",
                     "types", "typing", "shared", "src"}

    def _imports(self) -> list[str]:
        tree = ast.parse(COMPACT_PY.read_text(encoding="utf-8"))
        out: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                out += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                out.append(mod)
                if mod in ("src", "src.ui_v2", "shared"):
                    out += [f"{mod}.{a.name}" for a in node.names]
        return out

    def test_only_whitelisted_imports(self):
        for mod in self._imports():
            assert mod.split(".")[0] in self.ALLOWED_ROOTS, mod
            if mod.startswith("src."):
                assert mod.startswith("src.ui_v2"), mod
            if mod.startswith("shared"):
                assert mod in ("shared", "shared.ui_state"), mod

    @pytest.mark.parametrize("banned", ["streamlit", "src.data", "src.services", "src.ui.views",
                                        "_ui_kit", "src.compute"])
    def test_no_banned_import(self, banned):
        for mod in self._imports():
            assert banned not in mod, (banned, mod)

    def test_no_st_usage_and_no_signal_channel(self):
        tree = ast.parse(COMPACT_PY.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert node.id != "st"
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                assert node.value.id != "st"
        code_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                      and getattr(n.func, "id", getattr(n.func, "attr", "")) == "assert_signal_text_clean"]
        assert not code_calls

    def test_zero_production_caller(self):
        hits = []
        for p in list((ROOT / "src").rglob("*.py")) + [ROOT / "app.py"]:
            if p == COMPACT_PY or "__pycache__" in p.parts:
                continue
            t = p.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"ui_v2\.compact|ui_v2 import[^\n]*\bcompact\b|from\s+\.compact|from\s+src\.ui_v2\.compact", t):
                hits.append(str(p.relative_to(ROOT)))
        assert hits == [], hits


# ══════════════════════════════════════════════════════════════════
# META_KINDS（M2／M3）
# ══════════════════════════════════════════════════════════════════
def _contract_kinds() -> set[str]:
    text = CONTRACT.read_text(encoding="utf-8")
    sec = text.split("## §6 ", 1)[1].split("## §7 ", 1)[0]
    kinds: set[str] = set()
    for line in sec.splitlines():
        m = re.match(r"^\|\s*((?:`[a-z_]+`\s*/?\s*)+)\|", line)
        if m:
            kinds |= set(re.findall(r"`([a-z_]+)`", m.group(1)))
    kinds.discard("kind")
    return kinds


class TestMetaKinds:
    def test_keys_equal_contract_table(self):
        ck = _contract_kinds()
        assert len(ck) == 20, ck
        assert set(cp.META_KINDS) == ck

    def test_unregistered_kind_raises(self):
        for bad in ("made_up", "", "ASOF", "status", "guard_text"):
            with pytest.raises(ValueError):
                cp.meta_chip(bad, "x")
        with pytest.raises(ValueError):
            cp.meta_chip(None)  # type: ignore[arg-type]

    def test_unavailable_delegated(self):
        with pytest.raises(ValueError, match="status_chip"):
            cp.meta_chip("unavailable")
        c = cp.status_chip(us.UI_UNWIRED)
        assert c.text == "⛔ 未接線"

    def test_disjoint_from_badges(self):
        names = {b["name"] for b in components.BADGES}
        consts = {b["state_const"] for b in components.BADGES}
        assert not (set(cp.META_KINDS) & names)
        assert not (set(cp.META_KINDS) & consts)
        assert cp.KIND_STATUS not in cp.META_KINDS and cp.KIND_GUARD_TEXT not in cp.META_KINDS
        assert len(components.BADGES) == 11

    @pytest.mark.parametrize("state", sorted(us.UI_STATE_META))
    def test_status_chip_reads_ui_state_meta(self, state):
        name, glyph, _ = us.UI_STATE_META[state]
        if state == us.UI_PARTIAL:
            c = cp.status_chip(state, n=3, m=7)
            assert c.text == f"{glyph} 3／7 計入"
        else:
            c = cp.status_chip(state)
            assert c.text == f"{glyph} {name}"
        assert c.tone == state and c.kind == "status"

    def test_status_chip_fail_loud(self):
        with pytest.raises(ValueError):
            cp.status_chip("nope")
        with pytest.raises(ValueError):
            cp.status_chip(us.UI_PARTIAL)
        with pytest.raises(ValueError):
            cp.status_chip(us.UI_PARTIAL, n=5, m=3)
        with pytest.raises(ValueError):
            cp.status_chip(us.UI_IDLE, n=1, m=2)

    def test_fixed_texts_golden(self):
        want = {
            "asof_missing": "⬜ 資料日未提供", "readable": "✅ 可讀", "not_defined": "⬜ 尚未定義",
            "not_approved": "⬜ 尚未核准／無法判定", "estimated": "≈ 估算值", "proxy": "≈ 代理值",
            "imputed": "≈ 含補值", "data_quality": "⚠ 資料疑義", "pretax": "稅前",
            "ai": "🤖 AI 生成·非投資建議",
        }
        for k, t in want.items():
            assert cp.meta_chip(k).text == t, k

    def test_fixed_texts_match_existing_constants(self):
        mb = pytest.importorskip("src.ui.views._market_blocks")
        assert cp.meta_chip("not_defined").text == mb.NOT_DEFINED
        assert cp.meta_chip("not_approved").text == mb.WATER_VALUE
        assert cp.meta_chip("asof_missing").text == mb.DATA_DATE_NOT_PROVIDED

    def test_value_kinds_golden(self):
        assert cp.meta_chip("asof", "10/28").text == "🕒 資料 10/28"
        assert cp.meta_chip("asof", "2025/12/31").text == "🕒 資料 2025/12/31"
        assert cp.meta_chip("source", "Yahoo").text == "來源 Yahoo"
        assert cp.meta_chip("retrieved_at", "10/29 14:05").text == "抓取 10/29 14:05"
        assert cp.meta_chip("window", "近 252 日").text == "近 252 日"
        assert cp.meta_chip("stale", "7 天").text == "⚠ 過期 7 天"
        assert cp.meta_chip("stale").text == "⚠ 可能已過期"
        assert cp.meta_chip("freshness", "沿用前次").text == "⚠ 沿用前次"
        assert cp.meta_chip("coverage", "8／16 項有資料").text == "8／16 項有資料"

    def test_value_fail_loud(self):
        for kind in ("asof", "source", "window", "freshness", "coverage", "retrieved_at"):
            with pytest.raises(ValueError):
                cp.meta_chip(kind)                 # 缺值
            with pytest.raises(ValueError):
                cp.meta_chip(kind, "")             # 空字串
            with pytest.raises(ValueError):
                cp.meta_chip(kind, "   ")
            with pytest.raises(ValueError):
                cp.meta_chip(kind, 123)            # type: ignore[arg-type]
            with pytest.raises(ValueError):
                cp.meta_chip(kind, "a" * 13)       # >12 字
            with pytest.raises(ValueError):
                cp.meta_chip(kind, "a\nb")
        with pytest.raises(ValueError):
            cp.meta_chip("source", "⬜")             # 不得自帶第二套狀態符號
        with pytest.raises(ValueError):
            cp.meta_chip("readable", "x")            # 固定文字不接受 value
        with pytest.raises(ValueError):
            cp.meta_chip("not_defined", verbatim="改寫")
        with pytest.raises(ValueError):
            cp.meta_chip("asof", "10/28", verbatim="x")

    def test_verbatim_kinds_not_truncated_not_rewritten(self):
        fx = pytest.importorskip("shared.asset_currency_gate")
        c = cp.meta_chip("fx_partial", verbatim=fx.FX_PARTIAL_TEXT)
        assert c.text == fx.FX_PARTIAL_TEXT and len(c.text) > 12 and c.tone == "guard"
        c2 = cp.meta_chip("fx_partial", "3", verbatim=fx.FX_PARTIAL_TEXT)
        assert c2.text == fx.FX_PARTIAL_TEXT + "（3 檔）"
        for t in (fx.FX_TP_UNJUDGED_FOREIGN, fx.FX_TP_UNJUDGED_UNCONFIRMED):
            assert cp.meta_chip("fx_tp", verbatim=t).text == t
        with pytest.raises(ValueError):
            cp.meta_chip("fx_partial")
        with pytest.raises(ValueError):
            cp.meta_chip("fx_tp", verbatim="")
        with pytest.raises(ValueError):
            cp.meta_chip("fx_tp", "x", verbatim="停利未判：外幣")

    def test_guard_chip_verbatim(self):
        mb = pytest.importorskip("src.ui.views._market_blocks")
        c = cp.guard_chip(mb.CHART_A_MA_DISCLAIMER)
        assert c.text == mb.CHART_A_MA_DISCLAIMER == "均線為參考，不等於正式台股趨勢判斷。"
        with pytest.raises(ValueError):
            cp.guard_chip("")

    def test_chip_dataclass_rejects_inconsistent(self):
        with pytest.raises(ValueError):
            cp.Chip(kind="made_up", text="x", tone="info")
        with pytest.raises(ValueError):
            cp.Chip(kind="asof", text="x", tone="guard")
        with pytest.raises(ValueError):
            cp.Chip(kind="not_defined", text="x", tone="info")
        with pytest.raises(ValueError):
            cp.Chip(kind="status", text="x", tone="guard")
        with pytest.raises(ValueError):
            cp.Chip(kind="unavailable", text="x", tone="idle")
        with pytest.raises(ValueError):
            cp.Chip(kind="asof", text="", tone="info")
        assert not hasattr(cp.Chip("asof", "🕒 資料 10/28", "info"), "parts")   # D10(a)：無 parts


# ══════════════════════════════════════════════════════════════════
# chips_html（M16／M17／M19-列內、M2 護欄各自獨立）
# ══════════════════════════════════════════════════════════════════
def _chart_a_chips():
    return [
        cp.meta_chip("asof", "10/28"), cp.meta_chip("source", "Yahoo"),
        cp.meta_chip("window", "近 252 日"), cp.meta_chip("readable"),
        cp.guard_chip("均線為參考，不等於正式台股趨勢判斷。"), cp.meta_chip("not_defined"),
    ]


class TestChipsHtml:
    def test_chart_a_six_to_five_source_overflows(self):
        html, over = cp.chips_html(_chart_a_chips())
        assert [c.kind for c in over] == ["source"]            # D10(a)
        assert html.count('<span class="cp-chip') == 5
        assert "來源 Yahoo" not in html
        # 兩條護欄各自獨立、逐字、不合併
        assert html.count("cp-guard") == 2
        assert ">均線為參考，不等於正式台股趨勢判斷。<" in html and ">⬜ 尚未定義<" in html
        assert "均線為參考，不等於正式台股趨勢判斷。　" not in html

    def test_golden_chart_a(self):
        html, over = cp.chips_html(_chart_a_chips())
        assert html == (
            '<div class="cp-chips">'
            '<span class="cp-chip cp-info" data-kind="asof">🕒 資料 10/28</span>'
            '<span class="cp-chip cp-info" data-kind="window">近 252 日</span>'
            '<span class="cp-chip cp-status cp-t-green" data-kind="readable">✅ 可讀</span>'
            '<span class="cp-chip cp-guard" data-kind="guard_text">均線為參考，不等於正式台股趨勢判斷。</span>'
            '<span class="cp-chip cp-guard" data-kind="not_defined">⬜ 尚未定義</span></div>'
        )
        assert over == (cp.meta_chip("source", "Yahoo"),)

    def test_overflow_order_lowest_priority_first_never_guard(self):
        chips = [cp.meta_chip("retrieved_at", "10/29 14:05"), cp.meta_chip("source", "Yahoo"),
                 cp.meta_chip("window", "近 60 日"), cp.meta_chip("asof", "10/28"),
                 cp.status_chip(us.UI_DEGRADED), cp.meta_chip("not_defined")]
        html, over = cp.chips_html(chips, max_chips=3)
        assert {c.kind for c in over} == {"retrieved_at", "source", "window"}
        assert "cp-guard" in html and "資料 10/28" in html and "門檻已失準" in html

    def test_no_silent_truncation_overflow_returned(self):
        chips = [cp.meta_chip(k, v) for k, v in
                 (("asof", "10/28"), ("source", "TWSE"), ("window", "近 60 日"),
                  ("retrieved_at", "10/29 14:05"))] + [cp.meta_chip("readable"), cp.meta_chip("pretax")]
        html, over = cp.chips_html(chips)
        assert html.count('<span class="cp-chip') + len(over) == len(chips)

    def test_guard_overflow_raises_not_merged(self):
        guards = [cp.meta_chip(k) for k in ("not_defined", "not_approved", "estimated", "proxy",
                                            "imputed", "data_quality")]
        with pytest.raises(ValueError, match="護欄"):
            cp.chips_html(guards)
        with pytest.raises(ValueError):
            cp.chips_html(guards[:3], max_chips=2)

    def test_list_level_dedupe_rules(self):
        with pytest.raises(ValueError):
            cp.chips_html([cp.meta_chip("asof", "10/28"), cp.meta_chip("asof", "10/27")])
        with pytest.raises(ValueError):
            cp.chips_html([cp.meta_chip("asof", "10/28"), cp.meta_chip("asof_missing")])
        with pytest.raises(ValueError):
            cp.chips_html([cp.meta_chip("not_defined"), cp.meta_chip("not_defined")])
        with pytest.raises(ValueError):
            cp.chips_html([cp.meta_chip("window", "近 60 日"), cp.meta_chip("window", "近 30 日")])

    def test_bad_inputs(self):
        for bad in ("abc", None, (c for c in ()), [("x",)]):
            with pytest.raises(ValueError):
                cp.chips_html(bad)  # type: ignore[arg-type]
        for mc in (0, 6, True, "5", None):
            with pytest.raises(ValueError):
                cp.chips_html([], max_chips=mc)  # type: ignore[arg-type]
        assert cp.chips_html([]) == ("", ())

    def test_escape(self):
        c = cp.guard_chip('<img src=x onerror="a()">&')
        html, _ = cp.chips_html([c])
        assert "<img" not in html and "&lt;img" in html and "&quot;" in html and "&amp;" in html

    def test_cold_start_not_loaded_not_duplicated(self):
        # 冷啟動：chip 列只放護欄；未載入由槽承載（線框 §3.1）
        html, _ = cp.chips_html([cp.meta_chip("not_defined")])
        assert "尚未載入" not in html

    def test_chips_with_state_glyphs_do_not_raise(self):
        # M10：chip 走獨立 HTML，不經訊號文字頻道；⬜／🔴 不得 raise
        html, _ = cp.chips_html([cp.meta_chip("not_defined"), cp.status_chip(us.UI_FAILED)])
        assert "⬜" in html and "🔴" in html


# ══════════════════════════════════════════════════════════════════
# chart header（M7）
# ══════════════════════════════════════════════════════════════════
class TestChartHeader:
    SAY = "看台股目前是在長期上升、整理還是轉弱；趨勢與短期波動分開判斷。"

    def test_order_title_chips_say(self):
        html, over = cp.chart_header_html(title="圖A 🇹🇼 台股趨勢", chips=_chart_a_chips(), say=self.SAY,
                                          say_verbatim=True)
        i_t, i_c, i_s = html.index("cp-ch-title"), html.index("cp-chips"), html.index("cp-ch-say")
        assert i_t < i_c < i_s
        assert [c.kind for c in over] == ["source"]
        assert html.count("cp-ch-say") == 1

    def test_golden(self):
        html, _ = cp.chart_header_html(title="圖A", chips=[cp.meta_chip("not_defined")], say="一句話")
        assert html == (
            '<div class="cp-chart-header"><div class="cp-ch-title">圖A</div>'
            '<div class="cp-chips"><span class="cp-chip cp-guard" data-kind="not_defined">⬜ 尚未定義</span></div>'
            '<div class="cp-ch-say">一句話</div></div>'
        )
        assert _sha(html) == "f41aebe67fcc3992"

    def test_say_limits(self):
        with pytest.raises(ValueError):
            cp.chart_header_html(title="t", chips=[], say="字" * 33)
        cp.chart_header_html(title="t", chips=[], say="字" * 33, say_verbatim=True)   # 客戶原句豁免
        cp.chart_header_html(title="t", chips=[], say="字" * 32)
        with pytest.raises(ValueError):
            cp.chart_header_html(title="t", chips=[], say="a\nb")
        with pytest.raises(ValueError):
            cp.chart_header_html(title="t", chips=[], say="")
        html, _ = cp.chart_header_html(title="t", chips=[], say=None)
        assert "cp-ch-say" not in html and "cp-chips" not in html

    def test_title_required_and_escaped(self):
        with pytest.raises(ValueError):
            cp.chart_header_html(title="", chips=[], say=None)
        html, _ = cp.chart_header_html(title="<b>x</b>", chips=[], say="<i>")
        assert "<b>" not in html and "&lt;b&gt;" in html and "<i>" not in html


# ══════════════════════════════════════════════════════════════════
# Missing 槽（M14／M20／D6=B）
# ══════════════════════════════════════════════════════════════════
class TestMissingSlot:
    @pytest.mark.parametrize("state", [s for s in sorted(us.UI_STATE_META) if s not in (us.UI_LIVE, us.UI_PARTIAL)])
    def test_symbol_and_text_from_ui_state_meta(self, state):
        name, glyph, _ = us.UI_STATE_META[state]
        html = cp.chart_slot_missing_html(state, "原因甲", height_px=220)
        assert f"{glyph} {name}：原因甲" in html
        # M20：不得出現其他狀態的符號
        for other, (_n, g, _t) in us.UI_STATE_META.items():
            if other != state and g != glyph:
                assert g not in html, (state, g)

    def test_empty_state_does_not_draw_idle_symbol(self):
        assert "⬜" not in cp.chart_slot_missing_html("empty", "沒有資料", height_px=140)
        assert "▨" in cp.chart_slot_missing_html("empty", "沒有資料", height_px=140)

    def test_partial_needs_n_m(self):
        h = cp.chart_slot_missing_html("partial", "原因", variant="secondary", n=2, m=5)
        assert "◧ 2／5 計入：原因" in h
        with pytest.raises(ValueError):
            cp.chart_slot_missing_html("partial", "原因", variant="secondary")

    def test_primary_keeps_height_secondary_one_line(self):
        p = cp.chart_slot_missing_html("idle", "請按更新", height_px=220)
        assert 'cp-slot-primary' in p and "--cp-slot-h:220px" in p
        s = cp.chart_slot_missing_html("idle", "請按更新", variant="secondary")
        assert "cp-slot-line" in s and "style=" not in s and "⬜ 尚未載入：請按更新" in s   # 不隱藏 Missing
        assert p == ('<div class="cp-slot cp-slot-primary cp-s-grey" role="status" data-state="idle" '
                     'style="--cp-slot-h:220px"><span>⬜ 尚未載入：請按更新</span></div>')
        assert s == ('<div class="cp-slot cp-slot-line cp-s-grey" role="status" data-state="idle">'
                     '⬜ 尚未載入：請按更新</div>')

    def test_no_lines_points_axes(self):          # M14
        for variant, hp in (("primary", 220), ("secondary", None)):
            h = cp.chart_slot_missing_html("empty", "x", height_px=hp, variant=variant)
            for tag in ("<svg", "<polyline", "<path", "<circle", "<line", "<rect", "<canvas", "<img"):
                assert tag not in h

    def test_red_only_for_failed(self):
        for s in us.UI_STATE_META:
            if s in (us.UI_LIVE, us.UI_PARTIAL):
                continue
            h = cp.chart_slot_missing_html(s, "x", height_px=100)
            assert ("cp-s-red" in h) == (s == us.UI_FAILED), s
        assert 'role="alert"' in cp.chart_slot_missing_html("failed", "連線逾時", height_px=100)

    def test_fail_loud(self):
        with pytest.raises(ValueError):
            cp.chart_slot_missing_html("live", "x", height_px=100)
        with pytest.raises(ValueError):
            cp.chart_slot_missing_html("zzz", "x", height_px=100)
        for reason in ("", "  ", None, 5, "a\nb", "⬜ 尚未載入"):       # 自帶符號 → 兩種符號
            with pytest.raises(ValueError):
                cp.chart_slot_missing_html("idle", reason, height_px=100)  # type: ignore[arg-type]
        for hp in (None, 0, -1, 221, True, "220", 1.5):
            with pytest.raises(ValueError):
                cp.chart_slot_missing_html("idle", "x", height_px=hp)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            cp.chart_slot_missing_html("idle", "x", height_px=100, variant="secondary")
        with pytest.raises(ValueError):
            cp.chart_slot_missing_html("idle", "x", height_px=100, variant="tertiary")

    def test_reason_escaped(self):
        h = cp.chart_slot_missing_html("failed", "<script>x</script>", height_px=100)
        assert "<script>" not in h and "&lt;script&gt;" in h


# ══════════════════════════════════════════════════════════════════
# sparkline（M1）
# ══════════════════════════════════════════════════════════════════
def _spark(values, **kw):
    kw.setdefault("title", "VIX 近 30 日")
    kw.setdefault("missing_state", "empty")
    kw.setdefault("missing_text", "沒有資料")
    return cp.sparkline_svg(values, **kw)


def _nums(svg: str, tag: str, attr: str) -> list[float]:
    return [float(x) for x in re.findall(rf"<{tag}[^>]*\b{attr}=\"([-0-9.]+)\"", svg)]


class TestSparkline:
    def test_no_gap_single_polyline(self):
        svg = _spark([1, 2, 3, 2])
        assert svg.count("<polyline") == 1 and "<circle" not in svg
        pts = re.search(r'points="([^"]+)"', svg).group(1).split()
        assert len(pts) == 4
        assert pts[0].startswith("2.00,") and pts[-1].startswith("98.00,")

    def test_gap_middle_two_isolated_dots_no_line_x_preserved(self):   # M1 核心
        svg = _spark([1, NAN, 3])
        assert "<polyline" not in svg and svg.count("<circle") == 2
        assert _nums(svg, "circle", "cx") == [2.0, 98.0]   # 第 3 格仍在右端，不位移
        # 不補 0：y 範圍只由 1、3 決定（1 在底、3 在頂）
        cy = _nums(svg, "circle", "cy")
        assert cy == [46.0, 2.0]

    def test_none_gap_equals_nan_gap(self):
        assert _spark([None, 2, 4]) == _spark([NAN, 2, 4])
        svg = _spark([None, 2, 4])
        assert svg.count("<polyline") == 1
        # 第 1 格是缺口：線從第 2 格開始，x 保留原索引
        pts = re.search(r'points="([^"]+)"', svg).group(1).split()
        assert pts[0].startswith("50.00,") and pts[1].startswith("98.00,")

    def test_trailing_nan_one_segment(self):
        svg = _spark([1, 2, NAN])
        assert svg.count("<polyline") == 1 and "<circle" not in svg
        pts = re.search(r'points="([^"]+)"', svg).group(1).split()
        assert len(pts) == 2 and pts[0].startswith("2.00,") and pts[1].startswith("50.00,")

    def test_multiple_segments(self):
        svg = _spark([1, 2, NAN, 5, 6, 7, NAN, 3])
        assert svg.count("<polyline") == 2 and svg.count("<circle") == 1

    @pytest.mark.parametrize("vals", [[1, NAN, NAN], [NAN, NAN, NAN], [5], [], [None, None], [None, 3, NAN]])
    def test_fewer_than_two_valid_points_placeholder(self, vals):
        svg = _spark(vals, missing_state="idle", missing_text="請按更新")
        assert svg.placeholder is True
        for tag in ("<svg", "<polyline", "<path", "<circle", "<line"):
            assert tag not in svg
        assert "⬜ 尚未載入：請按更新" in svg

    def test_placeholder_symbol_follows_state(self):
        svg = _spark([NAN, NAN], missing_state="empty", missing_text="x")
        assert "▨ 無資料：x" in svg and "⬜" not in svg

    def test_flat_series_midline(self):
        svg = _spark([5, 5, 5])
        assert _nums(svg, "polyline", "points") == [] or True
        assert re.search(r'points="2.00,24.00 50.00,24.00 98.00,24.00"', svg)

    def test_no_numbers_shown(self):            # D5=A
        svg = _spark([10.5, 20.25, 15.0])
        assert "<text" not in svg
        visible = _strip_tags(svg.replace(f"<title>VIX 近 30 日</title>", ""))
        assert visible == ""

    def test_title_and_aria_escaped(self):
        svg = _spark([1, 2], title='a"<b>')
        assert "&quot;" in svg and "<b>" not in svg and "<title>" in svg

    def test_golden(self):
        svg = _spark([1, NAN, 3, 4, 2])
        assert isinstance(svg, cp.SafeHtml) and svg.placeholder is False
        assert _sha(svg) == "dac22fe206792bbe"

    def test_fail_loud_types(self):
        for bad in ([1, "2", 3], [1, True, 3], [1, math.inf], [1, -math.inf, 2], "123", None, (x for x in [1, 2]),
                    [1, object()]):
            with pytest.raises(ValueError):
                _spark(bad)   # type: ignore[arg-type]
        for kw in ({"w": 5}, {"h": 65}, {"h": 0}, {"w": True}, {"title": ""}, {"missing_text": ""},
                   {"missing_state": "nope"}, {"missing_state": "live"}, {"missing_state": "partial"}):
            with pytest.raises(ValueError):
                _spark([1, 2], **kw)   # 即使這次畫得出來，缺值參數也必須合法

    def test_tuple_and_numeric_types_ok(self):
        assert "<polyline" in _spark((1, 2.5, 3))

    def test_not_str_safehtml_distinction(self):
        assert isinstance(_spark([1, 2]), cp.SafeHtml) and not isinstance(str("x"), cp.SafeHtml)

    def test_safehtml_not_publicly_constructible_not_exported(self):     # F1
        with pytest.raises(ValueError):
            cp.SafeHtml("<script>")
        with pytest.raises(ValueError):
            cp.SafeHtml("<x>", _placeholder=True)
        assert "SafeHtml" not in cp.__all__
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="x", value="1", spark=cp.SafeHtml("<b>"),   # type: ignore[arg-type]
                             group_window_text="近 30 日")

    def test_placeholder_is_read_only(self):                               # F1
        sp = _spark([1, 2])
        ph = _spark([NAN, NAN], missing_state="idle", missing_text="x")
        assert sp.placeholder is False and ph.placeholder is True
        for obj in (sp, ph):
            with pytest.raises(AttributeError):
                obj.placeholder = not obj.placeholder                      # type: ignore[misc]
            with pytest.raises(AttributeError):
                obj._ph = True
        assert ph.placeholder is True and sp.placeholder is False


# ══════════════════════════════════════════════════════════════════
# KPI tile（M15／M19）
# ══════════════════════════════════════════════════════════════════
class TestKpiTile:
    def test_cold_start_golden(self):
        html = cp.kpi_tile_html(label="建議總持股水位", value=None, chips=[cp.meta_chip("not_approved")],
                                say="風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate", say_verbatim=True)
        assert html == (
            '<div class="cp-tile"><div class="cp-tile-label">建議總持股水位</div>'
            '<div class="cp-tile-value cp-blank"></div>'
            '<div class="cp-chips"><span class="cp-chip cp-guard" data-kind="not_approved">⬜ 尚未核准／無法判定</span></div>'
            '<div class="cp-tile-say">風險上限／獨立顯示待 C2b＋RC-VISIBILITY Gate</div></div>'
        )

    def test_value_none_never_zero(self):         # M15
        html = cp.kpi_tile_html(label="水位", value=None, chips=[cp.meta_chip("not_approved")])
        cell = re.search(r'<div class="cp-tile-value[^"]*">(.*?)</div>', html).group(1)
        assert cell == ""
        for bad in ("0", "—％", "中性"):
            assert bad not in cell

    def test_blank_requires_chip(self):
        with pytest.raises(ValueError, match="留白"):
            cp.kpi_tile_html(label="水位", value=None)

    def test_loaded_with_spark_and_badge(self):
        sp = _spark([1, 2, 3])
        html = cp.kpi_tile_html(label="市場位階", value="震盪", chips=[cp.meta_chip("window", "近 30 日")],
                                say="市場位階，不是台股趨勢", spark=sp, state_badge_n=1)
        assert "cp-tile-spark" in html and "bdg-1" in html and _strip_tags(re.sub(r"<svg.*?</svg>", "", html)).count("近 30 日") == 1
        assert _sha(html) == "6838f0377ebfeae8"

    @pytest.mark.parametrize("kind,val", [("asof", "10/28"), ("source", "TWSE"), ("retrieved_at", "10/29"),
                                          ("readable", None)])
    def test_asof_family_forbidden_in_tile(self, kind, val):     # M19
        with pytest.raises(ValueError, match="tile"):
            cp.kpi_tile_html(label="x", value="1", chips=[cp.meta_chip(kind, val)])

    def test_asof_missing_forbidden(self):
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="x", value="1", chips=[cp.meta_chip("asof_missing")])

    def test_group_asof_not_repeated(self):
        html = cp.kpi_tile_html(label="x", value="1", chips=[cp.meta_chip("window", "近 30 日")])
        assert "資料 " not in html

    def test_chip_count_rules(self):
        w, g, s = cp.meta_chip("window", "近 30 日"), cp.meta_chip("not_defined"), cp.status_chip(us.UI_DEGRADED)
        cp.kpi_tile_html(label="x", value="1", chips=[w, g])
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="x", value="1", chips=[w, g, s])
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="x", value="1", chips=[g, s])           # >1 狀態／護欄
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="x", value="1", chips=[w, cp.meta_chip("window", "近 60 日")])

    def test_window_same_as_group_forbidden(self):
        w = cp.meta_chip("window", "近 30 日")
        with pytest.raises(ValueError, match="組級"):
            cp.kpi_tile_html(label="x", value="1", chips=[w], group_window_text="近 30 日")
        cp.kpi_tile_html(label="x", value="1", chips=[w], group_window_text="近 252 日")

    def test_spark_requires_visible_window(self):
        sp = _spark([1, 2, 3])
        with pytest.raises(ValueError, match="窗口"):
            cp.kpi_tile_html(label="x", value="1", spark=sp)
        cp.kpi_tile_html(label="x", value="1", spark=sp, group_window_text="近 30 日")
        # placeholder 不需窗口
        ph = _spark([NAN, NAN], missing_state="idle", missing_text="請按更新")
        cp.kpi_tile_html(label="x", value="1", spark=ph)

    def test_spark_must_be_safehtml(self):
        with pytest.raises(ValueError, match="SafeHtml"):
            cp.kpi_tile_html(label="x", value="1", spark="<svg></svg>", group_window_text="近 30 日")  # type: ignore[arg-type]

    def test_value_and_face_limits(self):
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="x", value="1" * 13)
        cp.kpi_tile_html(label="x", value="1" * 12)
        with pytest.raises(ValueError, match="卡面"):
            cp.kpi_tile_html(label="標" * 8, value="值" * 12, chips=[cp.meta_chip("not_approved")],
                             say="句" * 32)
        # 客戶原句另計
        cp.kpi_tile_html(label="標" * 8, value="值" * 12, chips=[cp.meta_chip("not_approved")],
                         say="句" * 32, say_verbatim=True)

    def test_escape_and_types(self):
        html = cp.kpi_tile_html(label="<b>", value="<i>", say="<u>")
        assert "<b>" not in html and "<i>" not in html and "<u>" not in html
        for kw in ({"label": ""}, {"label": 5}, {"value": ""}, {"value": 5}, {"chips": "x"}, {"say": ""}):
            args = {"label": "x", "value": "1", **kw}
            with pytest.raises(ValueError):
                cp.kpi_tile_html(**args)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="x", value="1", state_badge_n=99)


# ══════════════════════════════════════════════════════════════════
# small multiples
# ══════════════════════════════════════════════════════════════════
class TestSmallMultiples:
    def _cells(self):
        return [cp.SmCell("道瓊", svg=_spark([1, 2, 3])), cp.SmCell("那指", svg=_spark([3, 2, 1])),
                cp.SmCell("費半", svg=None, missing_state="empty", missing_text="本輪沒有這個系列")]

    def test_golden_and_cols(self):
        html = cp.small_multiples_html(self._cells())
        assert html.startswith('<div class="cp-sm cp-sm-d3-m2">') and html.count("cp-sm-cell") == 3
        assert _sha(html) == "2b05d288c7db44ec"
        assert "cp-sm-d2-m1" in cp.small_multiples_html(self._cells(), cols_desktop=2, cols_mobile=1)

    def test_no_numbers_in_cells(self):        # D5=A
        cells = [cp.SmCell("道瓊", svg=_spark([100.5, 200.25, 150.0])), cp.SmCell("那指", svg=_spark([3, 2, 1]))]
        html = cp.small_multiples_html(cells)
        assert "<text" not in html
        visible = _strip_tags(re.sub(r"<title>.*?</title>", "", html))
        assert not re.search(r"\d", visible), visible

    def test_missing_cell_placeholder_honest(self):
        html = cp.small_multiples_html(self._cells())
        assert "▨ 無資料：本輪沒有這個系列" in html and html.count("<polyline") == 2

    def test_window_chip_only_window_kind(self):
        c = cp.SmCell("道瓊", svg=_spark([1, 2]), window_chip=cp.meta_chip("window", "近 60 日"))
        assert "近 60 日" in cp.small_multiples_html([c])
        with pytest.raises(ValueError):
            cp.small_multiples_html([cp.SmCell("x", svg=_spark([1, 2]), window_chip=cp.meta_chip("asof", "10/28"))])

    def test_fail_loud(self):
        sp = _spark([1, 2])
        bad_cells = [
            [], (), "x", None,
            [cp.SmCell("", svg=sp)], [cp.SmCell("字" * 9, svg=sp)],
            [cp.SmCell("a", svg="<svg/>")],                                  # type: ignore[arg-type]
            [cp.SmCell("a", svg=None)],                                      # 缺值參數
            [cp.SmCell("a", svg=sp, missing_state="idle", missing_text="x")],
            [cp.SmCell("a", svg=None, missing_state="live", missing_text="x")],
            ["not a cell"],
        ]
        for cells in bad_cells:
            with pytest.raises(ValueError):
                cp.small_multiples_html(cells)  # type: ignore[arg-type]
        for kw in ({"cols_desktop": 4}, {"cols_desktop": 0}, {"cols_mobile": 3}, {"cols_mobile": True}):
            with pytest.raises(ValueError):
                cp.small_multiples_html([cp.SmCell("a", svg=sp)], **kw)

    def test_name_escaped(self):
        html = cp.small_multiples_html([cp.SmCell("<b>", svg=_spark([1, 2]))])
        assert "<b>" not in html


# ══════════════════════════════════════════════════════════════════
# Top-N（M4）
# ══════════════════════════════════════════════════════════════════
class TestTopN:
    def test_identity_order_counts(self):
        rows = [{"k": i} for i in range(36)]
        r = cp.topn_view(rows, 5)
        assert len(r.shown) == 5 and r.hidden == 31 and r.total == 36
        for i in range(5):
            assert r.shown[i] is rows[i]
        assert r.more_text == "另 31 筆見全部" and r.all_label == "▸ 查看全部（36 筆）"
        assert len(rows) == 36 and rows[0] == {"k": 0}      # 不改動來源

    def test_n_larger_or_equal(self):
        rows = (1, 2, 3)
        r = cp.topn_view(rows, 10)
        assert r.shown == (1, 2, 3) and r.hidden == 0 and r.more_text is None and r.all_label is None
        assert cp.topn_view(rows, 3).hidden == 0

    def test_empty_rows(self):
        r = cp.topn_view([], 5)
        assert r.shown == () and r.hidden == 0 and r.total == 0

    def test_tuple_accepted_order_preserved_no_sort(self):
        rows = [3, 1, 2]
        assert cp.topn_view(rows, 2).shown == (3, 1)

    def test_fail_loud(self):
        for n in (0, -1, True, 1.5, "5", None):
            with pytest.raises(ValueError):
                cp.topn_view([1], n)  # type: ignore[arg-type]
        for rows in ((i for i in range(3)), "abc", {1, 2}, None, iter([1])):
            with pytest.raises(ValueError):
                cp.topn_view(rows, 2)  # type: ignore[arg-type]

    def test_l3_params_untouched(self):
        pf = pytest.importorskip("src.ui.views.page_find")
        assert pf.TOP_N_OPTIONS == (20, 50, 100) and pf.DEFAULT_TOP_N == 50


# ══════════════════════════════════════════════════════════════════
# segment_options（D8：純資料，不碰 streamlit）
# ══════════════════════════════════════════════════════════════════
class TestSegmentOptions:
    def test_normalize(self):
        s = cp.segment_options(["台股", "海外市場", "台股", "利率", "美元"], "利率")
        assert s.options == ("台股", "海外市場", "利率", "美元") and s.default == "利率" and s.default_index == 2

    def test_fail_loud(self):
        for opts in ([], ["a", ""], ["a", "  "], ["a", 1], "ab", None, (x for x in "ab")):
            with pytest.raises(ValueError):
                cp.segment_options(opts, "a")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            cp.segment_options(["a", "b"], "c")
        with pytest.raises(ValueError):
            cp.segment_options(["a", "b"], None)  # type: ignore[arg-type]


# ══════════════════════════════════════════════════════════════════
# compact_css（M9、D3）
# ══════════════════════════════════════════════════════════════════
def _rule(css: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", css)
    assert m, selector
    return m.group(1)


class TestCompactCss:
    css = cp.compact_css()

    def test_separate_from_page_css(self):
        assert ".cp-" not in markup.page_css("dark") and ".cp-" not in markup.page_css("light")
        assert "<style" not in self.css
        assert cp.compact_css() == self.css                  # 決定性

    def test_guard_solid_thick_never_dashed(self):          # D3=A
        guard = _rule(self.css, ".cp-guard")
        assert "2px solid" in guard and "dashed" not in guard and "dotted" not in guard
        assert "dashed" not in self.css and "dotted" not in self.css
        assert "1px solid" in _rule(self.css, ".cp-info")

    def test_stale_chip_uses_amber_not_red(self):            # M9
        stale = cp.meta_chip("stale", "7 天")
        html, _ = cp.chips_html([stale])
        cls = re.search(r'class="[^"]*(cp-t-[a-z]+)', html).group(1)
        body = _rule(self.css, "." + cls)
        assert "--sig-amber" in body and "--sig-red" not in body
        assert cls == "cp-t-amber"
        # 紅只出現在 failed 對應的兩條規則
        reds = [m.group(0) for m in re.finditer(r"[^{}]*\{[^}]*--sig-red[^}]*\}", self.css)]
        assert len(reds) == 2 and all(".cp-t-red" in r or ".cp-s-red" in r for r in reds)
        fh, _ = cp.chips_html([cp.status_chip(us.UI_FAILED)])
        assert "cp-t-red" in fh
        for s in us.UI_STATE_META:
            h, _ = cp.chips_html([cp.status_chip(s, n=1, m=2) if s == us.UI_PARTIAL else cp.status_chip(s)])
            assert ("cp-t-red" in h) == (s == us.UI_FAILED)

    def test_geometry_declared_root_and_mobile_media(self):
        root = _rule(self.css, ":root")
        for k, v in tokens.COMPACT_GEOMETRY.items():
            assert f"{k}:{v};" in root
        assert "@media (max-width:640px)" in self.css
        assert "cp-sm-d3-m2{grid-template-columns:repeat(3,minmax(0,1fr))}" in self.css
        assert "grid-template-columns:repeat(2,minmax(0,1fr))" in self.css.split("@media", 1)[1]

    def test_only_known_vars_referenced(self):
        declared = set(tokens.COMPACT_GEOMETRY) | set(tokens.DARK) | set(tokens.SPACING)
        for v in re.findall(r"var\((--[a-z0-9-]+)", self.css):
            assert v in declared or v == "--cp-slot-h", v      # --cp-slot-h 由元件 inline 設定

    def test_golden(self):
        assert _sha(self.css) == "157df4313b88b380"


# ══════════════════════════════════════════════════════════════════
# 2026-10-30 兩組獨立 QA 後的修正守衛（M1／M2／F1～F8／L1／L3／L4／Q46／Q57）
# ══════════════════════════════════════════════════════════════════
class TestChipDirectConstructionValidated:                    # F2／L1
    @pytest.mark.parametrize("kind", ["readable", "asof_missing", "not_defined", "not_approved",
                                      "estimated", "proxy", "imputed", "data_quality", "pretax", "ai"])
    def test_fixed_text_must_equal_template(self, kind):
        spec = cp.META_KINDS[kind]
        assert cp.Chip(kind, spec.template, spec.tone).text == spec.template      # 對的可建
        for bad in (spec.template + "!", "別的字", spec.template.replace("⬜", "").replace("✅", "").strip() or "x"):
            if bad == spec.template:
                continue
            with pytest.raises(ValueError):
                cp.Chip(kind, bad, spec.tone)

    def test_value_kind_must_match_template(self):
        cp.Chip("asof", "🕒 資料 10/28", "info")
        for kind, bad in (("asof", "資料 10/28"), ("asof", "🕒 資料 "), ("source", "Yahoo"),
                          ("stale", "過期 7 天"), ("freshness", "沿用前次"), ("retrieved_at", "抓取"),
                          ("asof", "🕒 資料 " + "a" * 13), ("asof", "🕒 資料 ⬜"), ("window", "近\n60 日")):
            tone = cp.META_KINDS[kind].tone
            with pytest.raises(ValueError):
                cp.Chip(kind, bad, tone)
        cp.Chip("stale", "⚠ 可能已過期", "degraded")                 # optional_value 的 fallback

    def test_status_text_must_derive_from_ui_state_meta(self):
        name, glyph, _ = us.UI_STATE_META[us.UI_IDLE]
        cp.Chip("status", f"{glyph} {name}", us.UI_IDLE)
        for bad_text, tone in ((f"{glyph} 隨便寫", us.UI_IDLE), (f"{glyph} {name}", us.UI_FAILED),
                               ("🔴 取得失敗", us.UI_IDLE), ("x", us.UI_IDLE), (f"{glyph} {name}", "info")):
            with pytest.raises(ValueError):
                cp.Chip("status", bad_text, tone)
        cp.Chip("status", "◧ 3／7 計入", us.UI_PARTIAL)
        for bad in ("◧ 7／3 計入", "◧ 03／7 計入", "◧ 3／0 計入", "◧ N／M 計入", "◧ 3／7"):
            with pytest.raises(ValueError):
                cp.Chip("status", bad, us.UI_PARTIAL)

    def test_tone_rules(self):
        with pytest.raises(ValueError):
            cp.Chip("stale", "⚠ 過期 7 天", "live")                     # stale 只能 degraded
        with pytest.raises(ValueError):
            cp.Chip("stale", "⚠ 過期 7 天", "failed")
        with pytest.raises(ValueError):
            cp.Chip("freshness", "⚠ 沿用前次", "idle")
        with pytest.raises(ValueError):
            cp.Chip("readable", "✅ 可讀", "degraded")                   # readable 只能 live
        with pytest.raises(ValueError):
            cp.Chip("coverage", "8／16 項有資料", "live")              # coverage 只能 partial
        with pytest.raises(ValueError):
            cp.Chip("guard_text", "紅色護欄", "failed")                  # 紅只給 status failed
        with pytest.raises(ValueError):
            cp.Chip("asof_missing", "⬜ 資料日未提供", "failed")
        f = cp.status_chip(us.UI_FAILED)
        assert f.tone == us.UI_FAILED

    def test_non_str_and_unhashable_are_valueerror_not_typeerror(self):
        for tone in ([], {}, ["info"], None, 1, ("info",)):
            with pytest.raises(ValueError):
                cp.Chip("asof", "🕒 資料 10/28", tone)                   # type: ignore[arg-type]
        for kind in ([], None, 3):
            with pytest.raises(ValueError):
                cp.Chip(kind, "x", "info")                              # type: ignore[arg-type]
        with pytest.raises(ValueError):
            cp.Chip("guard_text", ["x"], "guard")                       # type: ignore[arg-type]

    def test_guard_text_only_nonempty_single_line(self):
        cp.Chip("guard_text", "任何客戶逐字護欄句，不驗模板。", "guard")
        for bad in ("", "  ", "\u200b\u200b", "a\nb", "a\u2028b"):
            with pytest.raises(ValueError):
                cp.Chip("guard_text", bad, "guard")
        with pytest.raises(ValueError):
            cp.guard_chip("\u200b")

    def test_verbatim_fx_kinds_free_text_but_nonempty(self):
        cp.Chip("fx_tp", "停利未判：外幣", "guard")
        with pytest.raises(ValueError):
            cp.Chip("fx_tp", "", "guard")

    def test_every_factory_output_roundtrips_through_direct_construction(self):
        chips = [cp.meta_chip(k) for k, sp in cp.META_KINDS.items() if sp.mode == "fixed"]
        chips += [cp.meta_chip("stale"), cp.meta_chip("stale", "7 天"), cp.meta_chip("freshness", "沿用前次"),
                  cp.meta_chip("coverage", "8／16 項有資料"), cp.meta_chip("asof", "10/28"),
                  cp.meta_chip("fx_partial", verbatim="外幣部分"), cp.meta_chip("fx_partial", "3", verbatim="外幣部分"),
                  cp.guard_chip("逐字句")]
        chips += [cp.status_chip(s, n=1, m=2) if s == us.UI_PARTIAL else cp.status_chip(s) for s in us.UI_STATE_META]
        for c in chips:
            assert cp.Chip(c.kind, c.text, c.tone) == c


class TestChipRowExclusion:                                                  # F3
    def test_readable_vs_stale_like(self):
        for other in (cp.meta_chip("stale", "7 天"), cp.meta_chip("stale"), cp.meta_chip("freshness", "沿用前次"),
                      cp.meta_chip("coverage", "8／16 項有資料"), cp.status_chip(us.UI_DEGRADED),
                      cp.status_chip(us.UI_FAILED), cp.status_chip(us.UI_UNWIRED), cp.status_chip(us.UI_IDLE),
                      cp.status_chip(us.UI_PARTIAL, n=1, m=2)):
            with pytest.raises(ValueError):
                cp.chips_html([cp.meta_chip("readable"), other])
            with pytest.raises(ValueError):
                cp.chart_header_html(title="t", chips=[other, cp.meta_chip("readable")], say=None)

    def test_at_most_one_non_readable_status_chip(self):
        pairs = [(cp.meta_chip("stale"), cp.meta_chip("coverage", "8／16 項有資料")),
                 (cp.status_chip(us.UI_DEGRADED), cp.meta_chip("freshness", "沿用前次")),
                 (cp.meta_chip("asof_missing"), cp.status_chip(us.UI_EMPTY)),
                 (cp.status_chip(us.UI_IDLE), cp.status_chip(us.UI_FAILED))]
        for a, b in pairs:
            with pytest.raises(ValueError, match="狀態"):
                cp.chips_html([a, b])
            with pytest.raises(ValueError):
                cp.kpi_tile_html(label="x", value="1", chips=[a, b])

    def test_allowed_combinations_still_work(self):
        cp.chips_html([cp.meta_chip("readable"), cp.meta_chip("not_defined"), cp.meta_chip("asof", "10/28")])
        cp.chips_html([cp.meta_chip("stale", "7 天"), cp.meta_chip("not_defined"), cp.meta_chip("ai")])
        cp.chips_html([cp.meta_chip("readable"), cp.status_chip(us.UI_LIVE)])


class TestKpiBlankMustExplain:                                               # M1／F6
    def test_blank_with_only_window_or_info_raises(self):
        for chips in ([cp.meta_chip("window", "近 30 日")], [cp.meta_chip("pretax")], [cp.meta_chip("ai")],
                      [cp.meta_chip("window", "近 30 日"), cp.meta_chip("pretax")]):
            with pytest.raises(ValueError, match="留白"):
                cp.kpi_tile_html(label="x", value=None, chips=chips)

    def test_blank_with_live_status_does_not_explain(self):
        with pytest.raises(ValueError, match="留白"):
            cp.kpi_tile_html(label="x", value=None, chips=[cp.status_chip(us.UI_LIVE)])

    @pytest.mark.parametrize("chip", [cp.meta_chip("not_approved"), cp.meta_chip("not_defined"),
                                      cp.meta_chip("stale", "7 天"), cp.meta_chip("freshness", "沿用前次"),
                                      cp.meta_chip("coverage", "8／16 項有資料"), cp.status_chip(us.UI_IDLE),
                                      cp.status_chip(us.UI_FAILED), cp.status_chip(us.UI_UNWIRED),
                                      cp.guard_chip("逐字客戶護欄句"), cp.meta_chip("estimated")])
    def test_blank_with_explaining_chip_ok(self, chip):
        html = cp.kpi_tile_html(label="x", value=None, chips=[chip])
        assert "cp-blank" in html

    def test_blank_window_plus_guard_ok(self):
        cp.kpi_tile_html(label="x", value=None, chips=[cp.meta_chip("window", "近 30 日"), cp.meta_chip("not_defined")])


class TestKpiValueGuards:                                                    # L3
    @pytest.mark.parametrize("bad", ["—", "-", "--", "–", "—％", "—%", "－", "N/A", "n/a", "NA", "nan", "NaN",
                                     "None", "null", "NULL", "?", "？", "  —  ", "\u200b—", "％", "undefined"])
    def test_placeholder_values_rejected(self, bad):
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="x", value=bad)

    @pytest.mark.parametrize("ok", ["0", "0.0", "-1.2%", "震盪", "-3", "+0.5", "N/A 以外"])
    def test_real_values_kept_zero_is_truth(self, ok):
        assert f">{ok}</div>" in cp.kpi_tile_html(label="x", value=ok)

    def test_zero_width_value_is_empty(self):
        for bad in ("\u200b", "\ufeff\u200b ", ""):
            with pytest.raises(ValueError):
                cp.kpi_tile_html(label="x", value=bad)


class TestKpiFlagsAndBadge:                                                  # F7
    def test_badge_n_rejects_bool_and_illegal(self):
        for bad in (True, False, 0, 12, -1, "1", 1.0, None.__class__):
            with pytest.raises(ValueError):
                cp.kpi_tile_html(label="x", value="1", state_badge_n=bad)   # type: ignore[arg-type]
        assert "bdg-11" in cp.kpi_tile_html(label="x", value="1", state_badge_n=11)

    def test_say_verbatim_strict_bool(self):
        for bad in (1, 0, "yes", None, [], 1.0):
            with pytest.raises(ValueError):
                cp.kpi_tile_html(label="x", value="1", say="s", say_verbatim=bad)      # type: ignore[arg-type]
            with pytest.raises(ValueError):
                cp.chart_header_html(title="t", chips=[], say="s", say_verbatim=bad)   # type: ignore[arg-type]
        for bad in (1, "x", None):
            with pytest.raises(ValueError):
                cp.chart_header_html(title="t", chips=[], say=None, title_verbatim=bad)  # type: ignore[arg-type]

    def test_group_window_compare_normalised(self):
        w = cp.meta_chip("window", "近 30 日")
        for g in ("近 30 日", " 近 30 日 ", "近  30\u3000日", "近\u200b 30 日", "近 30 日"):
            with pytest.raises(ValueError, match="組級"):
                cp.kpi_tile_html(label="x", value="1", chips=[w], group_window_text=g)
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="x", value="1", group_window_text="\u200b")
        cp.kpi_tile_html(label="x", value="1", chips=[w], group_window_text="近 60 日")


class TestMissingTextNeverClipped:                                           # M2／F5
    @staticmethod
    def _rules_for(css: str, cls: str) -> list[str]:
        out = []
        for m in re.finditer(r"([^{}]+)\{([^}]*)\}", css):
            sels = [x.strip() for x in m.group(1).split(",")]
            if any(re.search(re.escape(cls) + r"(?![\w-])", x) for x in sels):
                out.append(m.group(2))
        return out

    @pytest.mark.parametrize("cls", [".cp-spark-missing", ".cp-sm-missing"])
    def test_css_never_clips_missing_reason(self, cls):
        rules = self._rules_for(cp.compact_css(), cls)
        assert rules, cls
        for body in rules:
            assert "overflow:hidden" not in body.replace(" ", ""), (cls, body)
            assert "overflow:clip" not in body.replace(" ", "")
            assert not re.search(r"(?<![-\w])height:\s*\d", body), (cls, body)      # 只能 min-height，不可固定 height
        assert "overflow:hidden" not in cp.compact_css().replace(" ", "").split(".cp-spark-missing{", 1)[1].split("}", 1)[0]

    def test_spark_placeholder_inline_style_min_height_not_fixed(self):
        ph = cp.sparkline_svg([NAN, NAN], title="t", missing_state="idle", missing_text="很長的原因" * 10)
        assert "min-height:48px" in ph and "overflow" not in ph
        assert not re.search(r"(?<![-\w])height:", re.search(r'style="([^"]*)"', ph).group(1))
        assert "很長的原因" * 10 in ph                                  # 原因文字完整，未截斷

    def test_sm_missing_text_full_and_wrapping_css(self):
        long = "這個系列本輪沒有資料的完整原因" * 4
        html = cp.small_multiples_html([cp.SmCell("x", svg=None, missing_state="empty", missing_text=long)])
        assert long in html
        css = cp.compact_css()
        assert "overflow-wrap:anywhere" in self._rules_for(css, ".cp-sm-missing")[0]
        assert "overflow-wrap:anywhere" in self._rules_for(css, ".cp-spark-missing")[0]


class TestSparklineFinite:                                                   # F4
    @pytest.mark.parametrize("vals", [[-1.7e308, 1.7e308], [1.7e308, -1.7e308, 0.0], [-1e308, 1e308, 5]])
    def test_non_finite_range_raises(self, vals):
        with pytest.raises(ValueError, match="非有限"):
            _spark(vals)

    def test_large_but_finite_ok(self):
        svg = _spark([1e300, 2e300, 1.5e300])
        assert "nan" not in svg.lower() and "inf" not in svg.lower()

    def test_tiny_range_ok_and_finite(self):
        svg = _spark([1.0, 1.0 + 2.2e-16, 1.0])
        assert "nan" not in svg.lower() and "inf" not in svg.lower()


class TestConstructionTimeValidation:                                        # F7
    def test_segment_spec_direct_construction(self):
        cp.SegmentSpec(("a", "b"), "b")
        for args in ((("a", "b"), "c"), ((), "a"), (("a", "a"), "a"), (("a", ""), "a"), (["a"], "a"),
                     (("a", "\u200b"), "a"), (("a", 1), "a"), (("a",), None)):
            with pytest.raises(ValueError):
                cp.SegmentSpec(*args)                                   # type: ignore[arg-type]

    def test_segment_zero_width_is_empty(self):
        with pytest.raises(ValueError):
            cp.segment_options(["a", "\u200b"], "a")

    def test_topn_direct_construction(self):
        cp.TopN(shown=(1, 2), hidden=3, total=5)
        for kw in (dict(shown=[1, 2], hidden=3, total=5), dict(shown=(1,), hidden=3, total=5),
                   dict(shown=(1,), hidden=-1, total=0), dict(shown=(), hidden=True, total=1),
                   dict(shown=(), hidden=0, total=-1), dict(shown=(1,), hidden=0, total=1.0)):
            with pytest.raises(ValueError):
                cp.TopN(**kw)                                           # type: ignore[arg-type]

    def test_small_multiples_duplicate_names_and_cols(self):
        sp = _spark([1, 2])
        with pytest.raises(ValueError, match="重複"):
            cp.small_multiples_html([cp.SmCell("道瓊", svg=sp), cp.SmCell("道瓊", svg=sp)])
        with pytest.raises(ValueError, match="重複"):
            cp.small_multiples_html([cp.SmCell("道瓊", svg=sp), cp.SmCell(" 道瓊 ", svg=sp)])
        with pytest.raises(ValueError, match="cols_mobile"):
            cp.small_multiples_html([cp.SmCell("a", svg=sp)], cols_desktop=1, cols_mobile=2)
        cp.small_multiples_html([cp.SmCell("a", svg=sp)], cols_desktop=2, cols_mobile=2)

    def test_title_length_cap_and_verbatim(self):
        cp.chart_header_html(title="字" * 40, chips=[], say=None)
        with pytest.raises(ValueError, match="標題"):
            cp.chart_header_html(title="字" * 41, chips=[], say=None)
        cp.chart_header_html(title="字" * 41, chips=[], say=None, title_verbatim=True)
        with pytest.raises(ValueError):
            cp.chart_header_html(title="\u200b", chips=[], say=None)
        with pytest.raises(ValueError):
            cp.chart_header_html(title="t", chips=[], say="\u200b")

    def test_zero_width_reason_is_empty(self):
        with pytest.raises(ValueError):
            cp.chart_slot_missing_html("idle", "\u200b", height_px=100)


class TestSlotAndTopNEdges:                                                  # L4
    @pytest.mark.parametrize("hp", [1, 50, 95])
    def test_primary_height_floor(self, hp):
        with pytest.raises(ValueError):
            cp.chart_slot_missing_html("idle", "x", height_px=hp)

    def test_primary_height_bounds_inclusive(self):
        assert "--cp-slot-h:96px" in cp.chart_slot_missing_html("idle", "x", height_px=96)
        assert "--cp-slot-h:220px" in cp.chart_slot_missing_html("idle", "x", height_px=220)

    def test_topn_empty_flag(self):
        e = cp.topn_view([], 5)
        assert e.empty is True and e.total == 0 and e.more_text is None
        assert cp.topn_view([1], 5).empty is False
        assert "Missing" in (cp.topn_view.__doc__ or "") and "Missing" in (cp.TopN.empty.__doc__ or "")

    def test_chart_header_doc_states_chip_floor_is_callers(self):
        assert "下限由呼叫端負責" in (cp.chart_header_html.__doc__ or "")
        html, over = cp.chart_header_html(title="t", chips=[], say=None)   # 0 顆不報錯（由呼叫端負責）
        assert "cp-chips" not in html and over == ()


class TestOverflowPriority:                                                  # F8／Q57／Q46
    def test_ai_and_pretax_not_pushed_out_before_asof(self):
        chips = [cp.meta_chip("asof", "10/28"), cp.meta_chip("window", "近 60 日"), cp.meta_chip("source", "TWSE"),
                 cp.meta_chip("ai"), cp.meta_chip("pretax"), cp.status_chip(us.UI_DEGRADED)]
        html, over = cp.chips_html(chips, max_chips=4)
        assert {c.kind for c in over} == {"window", "source"}
        assert "AI 生成" in html and "稅前" in html and "資料 10/28" in html

    def test_ai_pretax_same_rank_as_status(self):
        assert cp.meta_chip("ai").rank == cp.meta_chip("pretax").rank == cp.status_chip(us.UI_IDLE).rank == 1
        assert cp.meta_chip("asof", "10/28").rank > cp.meta_chip("ai").rank

    def test_guard_still_moved_out_last(self):
        chips = [cp.meta_chip("ai"), cp.meta_chip("pretax"), cp.meta_chip("not_defined"),
                 cp.meta_chip("asof", "10/28"), cp.meta_chip("source", "TWSE")]
        html, over = cp.chips_html(chips, max_chips=3)
        assert "cp-guard" in html and {c.kind for c in over} == {"asof", "source"}
        html2, over2 = cp.chips_html(chips, max_chips=1)
        assert "cp-guard" in html2 and {c.kind for c in over2} == {"ai", "pretax", "asof", "source"}

    def test_same_rank_tiebreak_later_in_list_overflows_first(self):         # Q57
        a, b, c = cp.meta_chip("ai"), cp.meta_chip("pretax"), cp.status_chip(us.UI_DEGRADED)
        assert a.rank == b.rank == c.rank
        html, over = cp.chips_html([a, b, c], max_chips=2)
        assert over == (c,)
        html, over = cp.chips_html([c, a, b], max_chips=2)
        assert over == (b,)
        # 外露者保持呼叫端相對順序
        assert html.index("data-kind=\"status\"") < html.index("data-kind=\"ai\"")
        sources = [cp.meta_chip("window", "近 30 日")]                       # 同 rank 的單例 kind 不可能重複，改用護欄
        g = [cp.meta_chip("not_defined"), cp.meta_chip("estimated"), cp.meta_chip("proxy")]
        html, over = cp.chips_html(g, max_chips=3)
        assert over == () and html.index("尚未定義") < html.index("估算值") < html.index("代理值")
        assert sources

    def test_status_symbol_comes_from_l0_via_monkeypatch(self, monkeypatch):    # Q46
        name, glyph, tr = us.UI_STATE_META[us.UI_IDLE]
        monkeypatch.setitem(us.UI_STATE_META, us.UI_IDLE, (name + "乙", "Ⓧ", tr))
        c = cp.status_chip(us.UI_IDLE)
        assert c.text == f"Ⓧ {name}乙"
        assert cp.Chip("status", c.text, c.tone) == c                        # 直接建構也跟著 L0
        with pytest.raises(ValueError):
            cp.Chip("status", f"{glyph} {name}", us.UI_IDLE)                 # 舊字不再合法
        slot = cp.chart_slot_missing_html(us.UI_IDLE, "原因", height_px=100)
        assert f"Ⓧ {name}乙：原因" in slot and glyph not in slot
        sp = cp.sparkline_svg([None, None], title="t", missing_state=us.UI_IDLE, missing_text="原因")
        assert f"Ⓧ {name}乙：原因" in sp
        with pytest.raises(ValueError):                                      # 新符號也進「不得自帶」名單
            cp.chart_slot_missing_html(us.UI_EMPTY, "Ⓧ 原因", height_px=100)


# ══════════════════════════════════════════════════════════════════
# 工程字樣（契約 §18）——掃**實際輸出**，不只掃模板
# ══════════════════════════════════════════════════════════════════
def _contract_18_terms() -> list[str]:
    text = CONTRACT.read_text(encoding="utf-8")
    line = next(ln for ln in text.splitlines() if ln.startswith("- **一律下沉或改白話**"))
    terms = re.findall(r"`([^`]+)`", line) + re.findall(r"「([^」]+)」", line)
    return [t for t in terms if t not in ("L0", "L6", "Lx")]


def _all_outputs() -> list[str]:
    outs: list[str] = []
    chips = [cp.meta_chip(k) for k, sp in cp.META_KINDS.items() if sp.mode == "fixed"]
    chips += [cp.meta_chip("stale"), cp.meta_chip("stale", "7 天"), cp.meta_chip("asof", "10/28"),
              cp.meta_chip("source", "Yahoo"), cp.meta_chip("retrieved_at", "10/29"),
              cp.meta_chip("window", "近 60 日"), cp.meta_chip("coverage", "8／16 項有資料"),
              cp.meta_chip("freshness", "沿用前次")]
    chips += [cp.status_chip(s, n=1, m=2) if s == us.UI_PARTIAL else cp.status_chip(s) for s in us.UI_STATE_META]
    for c in chips:
        outs.append(c.text)
    for c in chips[:1]:
        outs.append(cp.chips_html([c])[0])
    outs.append(cp.chart_header_html(title="圖A", chips=[cp.meta_chip("not_defined")], say="一句話")[0])
    outs.append(cp.kpi_tile_html(label="水位", value=None, chips=[cp.meta_chip("not_approved")]))
    outs.append(cp.kpi_tile_html(label="市場", value="震盪", chips=[cp.meta_chip("window", "近 30 日")],
                                 spark=_spark([1, 2, 3]), say="一句"))
    for st in us.UI_STATE_META:
        if st in (us.UI_LIVE, us.UI_PARTIAL):
            continue
        outs.append(cp.chart_slot_missing_html(st, "原因", height_px=120))
        outs.append(cp.chart_slot_missing_html(st, "原因", variant="secondary"))
        outs.append(str(_spark([NAN, NAN], missing_state=st, missing_text="原因")))
    outs.append(cp.small_multiples_html([cp.SmCell("a", svg=_spark([1, 2])),
                                         cp.SmCell("b", svg=None, missing_state="empty", missing_text="原因")]))
    t = cp.topn_view(list(range(30)), 5)
    outs += [t.more_text or "", t.all_label or "", cp.TOPN_MORE_FMT, cp.TOPN_ALL_LABEL_FMT]
    return outs


class TestNoEngineeringWording:
    def test_contract_18_list_parsed(self):
        terms = _contract_18_terms()
        assert {"線框", "SSOT", "widget", "expander", "service", "helper", "unwired", "鐵律"} <= set(terms), terms

    def test_default_texts_clean(self):
        for spec in cp.META_KINDS.values():
            for s in (spec.template, spec.fallback):
                if s:
                    for bad in ("L1", "L2", "L3", "service", "helper", "SSOT", "fetcher"):
                        assert bad not in s

    def test_real_outputs_have_no_engineering_words(self):
        terms = _contract_18_terms() + ["fetcher", "Gate", "葉1", "葉2", "取數接線揭露"]
        for out in _all_outputs():
            visible = _strip_tags(out)
            assert not re.search(r"\bL[0-6x]\b", visible), visible
            for t in terms:
                assert t not in visible, (t, visible)

    def test_scanner_would_catch_a_bad_word(self):            # 掃描器本身自證（避免掃空）
        h, _ = cp.chart_header_html(title="L3 service 取數", chips=[], say=None)
        assert re.search(r"\bL[0-6x]\b", _strip_tags(h)) and "service" in _strip_tags(h)
        assert len(_all_outputs()) > 30


class TestQaRound2Hardening:
    """複驗 QA 第二輪 A～G：偽造／極端輸入必須 ValueError（臨時 mutation 驗證必紅）。"""

    # C：SafeHtml 偽造
    def test_c_forged_safehtml_str_new_rejected(self):
        fake = str.__new__(cp.SafeHtml, "<svg/>")                   # 沒有 _ph
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="水位", value="1", spark=fake)
        with pytest.raises(ValueError):
            cp.small_multiples_html([cp.SmCell(name="A", svg=fake)])

    def test_c_non_bool_ph_rejected(self):
        bad = _spark([1, 2, 3])
        object.__setattr__(bad, "_ph", "yes")
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="水位", value="1", chips=[cp.meta_chip("window", "近 30 日")], spark=bad)
        with pytest.raises(ValueError):
            cp.small_multiples_html([cp.SmCell(name="A", svg=bad)])

    def test_c_genuine_safehtml_still_ok(self):
        cp.small_multiples_html([cp.SmCell(name="A", svg=_spark([1, 2, 3]))])

    # B：超大 int
    def test_b_huge_int_is_valueerror(self):
        with pytest.raises(ValueError):
            _spark([1, 10**400, 3])

    # A：object.__setattr__ 偽造 chip
    def test_a_forged_chip_blocked_before_output(self):
        c = cp.meta_chip("asof", "10/28")
        object.__setattr__(c, "text", "<script>")
        with pytest.raises(ValueError):
            cp._chip_span(c)
        with pytest.raises(ValueError):
            cp.chips_html([c])
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="水位", value="1", chips=[c])

    def test_a_forged_tone_and_kind_blocked(self):
        c = cp.meta_chip("not_defined")
        object.__setattr__(c, "tone", "failed")
        with pytest.raises(ValueError):
            cp.chips_html([c])
        c2 = cp.meta_chip("asof", "10/28")
        object.__setattr__(c2, "kind", "nope")
        with pytest.raises(ValueError):
            cp.chips_html([c2])

    # D：coverage 兩種契約形式（§6 表）；其餘 ValueError
    @pytest.mark.parametrize("v", ["8／16 項", "全部完整", "5／3", "8／16 項有資料 ✅ 可讀", "8/16", "08／16", "8／0",
                                   "８／１６", "-1／3", "8／", "8／16 項有資料 ", "3 項未評估 x", "-1 項未評估",
                                   "03 項未評估", "３ 項未評估", "項未評估", "任意文字"])
    def test_d_coverage_strict(self, v):
        with pytest.raises(ValueError):
            cp.meta_chip("coverage", v)
        with pytest.raises(ValueError):
            cp.Chip("coverage", v, "partial")

    @pytest.mark.parametrize("v", ["8／16 項有資料", "8／16", "0／16", "16／16", "1／1", "0 項未評估", "3 項未評估",
                                   "12 項未評估"])
    def test_d_coverage_ok(self, v):
        assert cp.meta_chip("coverage", v).text == v
        assert cp.Chip("coverage", v, "partial").text == v

    # E：stale／freshness 不得含可讀符號
    @pytest.mark.parametrize("kind", ["stale", "freshness"])
    @pytest.mark.parametrize("v", ["✅ 可讀", "✅", "可讀", "✔ 7 天"])
    def test_e_readable_symbol_banned(self, kind, v):
        with pytest.raises(ValueError):
            cp.meta_chip(kind, v)
        with pytest.raises(ValueError):
            cp.Chip(kind, f"⚠ {v}" if kind == "freshness" else f"⚠ 過期 {v}", "degraded")

    # F：不可見字元
    @pytest.mark.parametrize("ch", ["ㅤ", "⠀", "ᅟ", "ᅠ"])
    def test_f_invisible_is_empty(self, ch):
        assert ch in cp._INVISIBLE
        with pytest.raises(ValueError):
            cp._check_str("x", ch * 3)
        with pytest.raises(ValueError):
            cp.kpi_tile_html(label="水位", value=ch)

    # G：占位主值
    @pytest.mark.parametrize("v", ["暫無", "無資料", "無", "尚無", "N. A.", "n.a.", "暫 無", "無 資 料", "無。", "…", "暫無資料"])
    def test_g_placeholder_values(self, v):
        with pytest.raises(ValueError, match="占位"):
            cp.kpi_tile_html(label="水位", value=v)

    def test_g_real_values_still_ok(self):
        for v in ("0", "震盪", "無風險"):
            cp.kpi_tile_html(label="水位", value=v)
