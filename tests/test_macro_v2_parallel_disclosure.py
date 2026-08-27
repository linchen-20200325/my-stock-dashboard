"""tests/test_macro_v2_parallel_disclosure.py — D1 並列揭露 + 正名守衛（2026-08-27）

## 這一檔在守什麼

客戶 2026-08-27 裁示：**「同意 D1 替代方案：採並列揭露，並將 v2 正名為
「指標危險度」。」** 線框原本寫「先驗證、再合併」，驗證做完
（`scratchpad/verify_regime_paths.md`）結論是**不該合併**：

  · 兩條路徑不是同一個量。`allocation_service.get_macro_regime()` 算**多空位階**
    （吃 `warroom_summary` 4 個欄位 + `macro_state.json`）；
    `tab_macro_v2.overall_verdict()` 算**危險度彙總**（16 盞燈 worst-of）。
  · 實跑 400 組格點：燈色不一致 158/400（39.5%）、方向相反 18 組。
  · 16 盞燈逐一單獨轉紅，位階那條有 15 次完全不動。
  · 最容易對打的**不是極端值，是健康的多頭**（多頭走久 BIAS240 必然放大、
    融資餘額恆紅）。合併等於宣稱「沒有指標踩線＝多頭」。

本檔守三件事，**三件都不會讓畫面看起來壞掉**，所以只能靠測試釘住：

1. **正名** —— 那張卡不得再叫「總經位階」。名字錯 ＝ 一個錯誤判讀常駐在 UI 上。
2. **並列** —— 位階必須真的印出來。少印 ＝ 客戶核准的東西沒交付，而畫面完好如初。
3. **不調和** —— 兩個判斷誰都不准覆蓋誰、不准合成第三個燈。**並列的價值就在於
   保留分歧**；調和掉會把 `regime_arbiter` 剛收掉的多來源問題重新製造一個。

外加第 4 件：**位階未載入時要誠實**（不留白、不拿危險度的燈冒充）。

⚠️ 本檔預設 lane 只測純函式與原始碼守衛，**不啟動 Streamlit runtime**；
   真的把卡片渲染出來的那條在 slow lane（見檔尾 `TestRuntimeCard`）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

_L5 = pathlib.Path("src/ui/tabs/tab_macro_v2.py")
_L4 = pathlib.Path("src/ui/render/macro_v2_cards.py")

#: 位階那條的四種代表性回傳（`get_macro_regime()` 的契約子集，欄位名照抄）。
_REGIMES = {
    "bull": {"regime": "bull", "light": "🟢", "source": "bull:score",
             "is_loaded": True},
    "neutral": {"regime": "neutral", "light": "🟡",
                "source": "neutral:fallthrough", "is_loaded": True},
    "bear": {"regime": "bear", "light": "🔴", "source": "bear:trend_regime",
             "is_loaded": True},
    "unloaded": {"regime": "unknown", "light": "⬜", "source": "unloaded",
                 "is_loaded": False},
}
_BANDS = ("green", "yellow", "red", "gray")


def _fn(src: str, name: str) -> ast.FunctionDef:
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"找不到函式 {name}()")


def _names(node: ast.AST) -> set[str]:
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            out.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            out.add(sub.attr)
        elif isinstance(sub, ast.alias):
            out.add(sub.name.split(".")[-1])
    return out


# ════════════════════════════════════════════════════════════════
# 一、正名：那張卡叫「指標危險度」，不叫「總經位階」
# ════════════════════════════════════════════════════════════════
class TestRename:

    def test_the_title_constant_is_the_name_the_client_chose(self):
        """客戶原話指定的字串。改字之前先回去看客戶那句話。"""
        from src.ui.tabs.tab_macro_v2 import DANGER_TITLE
        assert DANGER_TITLE == "指標危險度"

    def test_the_card_label_no_longer_says_regime(self):
        """反向守衛：舊標籤不得回來。

        **突變測試的第一顆**：把 `<p class="v2-t">{DANGER_TITLE}</p>` 改回
        `<p class="v2-t">總經位階</p>`，本條轉紅。
        """
        src = _L5.read_text(encoding="utf-8")
        assert "總經位階</p>" not in src, "第 1 層標題卡又叫回「總經位階」了"
        assert ">總經位階<" not in src

    def test_the_render_uses_the_constant_not_a_literal(self):
        """標題走常數 —— 寫死字面值就會有第二個名字可以漂移。"""
        assert "DANGER_TITLE" in _names(_fn(_L5.read_text(encoding="utf-8"),
                                            "render_tab_macro_v2"))

    @staticmethod
    def _visible_strings() -> list[str]:
        """收集**會被印到畫面上**的字串常數。

        只看兩處：`render_tab_macro_v2()` 內的字面值，以及模組層那幾個
        `*_NOTE` 常數（它們被送進 `st.caption`）。**刻意不掃註解與 docstring**
        —— 那裡本來就必須談「舊名為什麼是錯的」，掃進去等於禁止解釋自己。
        """
        import src.ui.tabs.tab_macro_v2 as t
        node = _fn(_L5.read_text(encoding="utf-8"), "render_tab_macro_v2")
        out = [c.value for c in ast.walk(node)
               if isinstance(c, ast.Constant) and isinstance(c.value, str)]
        out += [getattr(t, n) for n in dir(t) if n.endswith("_NOTE")]
        out.append(t.DANGER_TITLE)
        return out

    def test_no_visible_string_calls_the_danger_roll_up_a_regime(self):
        """畫面上的字不得把 16 盞燈的 worst-of 叫成「位階」。

        註解 / docstring 不在射程內（那裡要解釋正名這件事本身）；這一條只管
        **使用者真的會讀到的字**。
        """
        bad = [v for v in self._visible_strings()
               if "總經位階" in v or "全域位階" in v]
        assert not bad, f"畫面字串把危險度叫成位階：{bad}"

    def test_the_band_glyphs_live_in_l4(self):
        """比色用的 emoji 字面住在 L4（本頁所有標籤的家）。

        L5 自己寫一份 emoji 會撞上 `TestStateColumnDualCoding` 的既有守衛，
        而且會變成第二把尺。**比較邏輯**仍在 L5 —— 只有那裡看得到兩個判斷。
        """
        from src.ui.render.macro_v2_cards import BAND_LIGHT
        assert set(BAND_LIGHT) == set(_BANDS)
        node = _fn(_L5.read_text(encoding="utf-8"), "parallel_verdict")
        assert "BAND_LIGHT" in _names(node), "L5 沒有用 L4 的字面"

    def test_the_caption_disclaims_the_direction_reading(self):
        """光改標題不夠 —— 副標必須明說**不含多空方向**。

        名字對了但副標仍寫「與總經頁同一套判定」，讀者照樣會把紅燈讀成
        空頭。這一條守的是「正名週邊文案」那一半。
        """
        caps = [v for v in self._visible_strings() if "worst-of" in v]
        assert caps, "第 1 層的副標不見了"
        assert any("不含多空方向" in v for v in caps),             "副標沒有講清楚危險度不含多空方向"


# ════════════════════════════════════════════════════════════════
# 二、並列：位階必須真的被讀出來、印出來
# ════════════════════════════════════════════════════════════════
class TestParallelIsWired:

    def test_the_tab_reads_the_single_source_of_truth(self):
        """`get_macro_regime()` 是全站唯一出處，本頁**唯讀取用**。

        **突變測試的第二顆**：把 `render_tab_macro_v2` 裡的
        `get_macro_regime()` / `parallel_verdict()` / `render_regime_parallel()`
        任一拿掉，本條轉紅。
        """
        used = _names(_fn(_L5.read_text(encoding="utf-8"), "render_tab_macro_v2"))
        for need in ("get_macro_regime", "parallel_verdict",
                     "render_regime_parallel"):
            assert need in used, f"第 1 層沒有接 {need} —— 並列揭露沒有交付"

    def test_the_l4_renderer_exists_and_prints_the_regime(self):
        l4 = _L4.read_text(encoding="utf-8")
        node = _fn(l4, "render_regime_parallel")
        assert "市場位階" in ast.unparse(node), "L4 沒有印出位階的標題"
        from src.ui.render import macro_v2_cards
        assert hasattr(macro_v2_cards, "render_regime_parallel")

    def test_the_tab_never_recomputes_the_regime_itself(self):
        """唯讀 ＝ 不得繞過 L3 自己去打仲裁器。

        直接 import `macro_state_locker` / `regime_arbiter` 就是第二條路徑，
        本頁與全站其餘 15 個消費端立刻可以漂移。
        """
        used = _names(ast.parse(_L5.read_text(encoding="utf-8")))
        for banned in ("macro_state_locker", "regime_arbiter",
                       "arbitrate_regime", "get_macro_state"):
            assert banned not in used, f"tab_macro_v2 不該碰 {banned}（唯讀走 L3）"

    def test_the_note_says_the_two_look_at_different_things(self):
        """不同色時的說明**必須**講「它們看的不是同一件事」。

        少了這句，使用者會把分歧讀成系統自相矛盾，然後開始猜哪個才對 ——
        而正確答案是兩個都對。
        """
        from src.ui.tabs.tab_macro_v2 import DIVERGENCE_NOTE
        assert "不是同一件事" in DIVERGENCE_NOTE
        assert "不含多空方向" in DIVERGENCE_NOTE
        for token in ("VIX", "PMI", "CPI", "融資"):
            assert token in DIVERGENCE_NOTE, f"沒講位階看不到 {token}"

    def test_same_colour_is_not_sold_as_agreement(self):
        """同色時也要講清楚**不是同一個判斷** —— 否則下次分開時會被讀成故障。"""
        from src.ui.tabs.tab_macro_v2 import AGREE_NOTE
        assert "不代表" in AGREE_NOTE and "不做任何調和" in AGREE_NOTE

    @pytest.mark.parametrize("band,reg,expect", [
        ("red", "bull", "DIVERGENCE_NOTE"),
        ("green", "bear", "DIVERGENCE_NOTE"),
        ("green", "bull", "AGREE_NOTE"),
        ("yellow", "neutral", "AGREE_NOTE"),
        ("red", "unloaded", "REGIME_UNLOADED_NOTE"),
        ("gray", "bull", "DANGER_UNLOADED_NOTE"),
        ("gray", "unloaded", "REGIME_UNLOADED_NOTE"),
    ])
    def test_note_selection(self, band, reg, expect):
        import src.ui.tabs.tab_macro_v2 as t
        pv = t.parallel_verdict(band, "detail", _REGIMES[reg])
        assert pv.note == getattr(t, expect)

    def test_the_healthy_bull_case_from_the_verification_report(self):
        """驗證報告 T8 的那一組：🟢 多頭 ＋ 🔴 危險度。

        BIAS240 22% ＋ 融資 5,148 億 → 危險度紅；趨勢 bull / score 5 /
        health 66 → 位階綠。**兩顆燈都要留著，而且要有話說。**
        """
        from src.ui.tabs.tab_macro_v2 import DIVERGENCE_NOTE, parallel_verdict
        pv = parallel_verdict("red", "2 桶紅　·　最差是「資金面」",
                              _REGIMES["bull"])
        assert pv.danger_light == "🔴" and pv.regime_light == "🟢"
        assert pv.note is DIVERGENCE_NOTE


# ════════════════════════════════════════════════════════════════
# 三、不調和：誰都不准覆蓋誰、不准合成第三個燈
# ════════════════════════════════════════════════════════════════
class TestNoReconciliation:
    """**突變測試的第三顆**在這一節。

    把兩個判斷調和成一個（例如讓危險度取 worst-of(危險度, 位階)、
    或讓位階在危險度紅時降級），下面任一條轉紅。
    """

    def test_the_danger_verdict_is_untouched_by_the_regime(self):
        from src.ui.tabs.tab_macro_v2 import parallel_verdict
        for band in _BANDS:
            seen = {
                (pv.danger_band, pv.danger_light, pv.danger_zh, pv.danger_color,
                 pv.danger_detail)
                for pv in (parallel_verdict(band, "D", r)
                           for r in _REGIMES.values())
            }
            assert len(seen) == 1, f"band={band} 的危險度隨位階變了：{seen}"
            assert next(iter(seen))[0] == band

    def test_the_regime_is_untouched_by_the_danger_verdict(self):
        from src.ui.tabs.tab_macro_v2 import parallel_verdict
        for key, reg in _REGIMES.items():
            seen = {
                (pv.regime_light, pv.regime_zh, pv.regime_source,
                 pv.regime_loaded)
                for pv in (parallel_verdict(b, "D", reg) for b in _BANDS)
            }
            assert len(seen) == 1, f"regime={key} 隨危險度變了：{seen}"
            assert next(iter(seen))[0] == reg["light"]

    def test_no_field_merges_the_two(self):
        """全 16 組交叉：每個欄位只能被「自己那一半」決定。

        做法是把欄位分成兩組，各自檢查它在**另一半**變動時是否恆定。
        新增一個同時吃兩邊的欄位（＝合併燈）會讓本條轉紅。
        """
        import dataclasses

        from src.ui.tabs.tab_macro_v2 import ParallelVerdict, parallel_verdict
        fields = [f.name for f in dataclasses.fields(ParallelVerdict)]
        # `note` 是**刻意**吃兩邊的欄位 —— 但它是「說明文字」，不是判斷。
        assert set(fields) - {"note"} == {
            "danger_band", "danger_light", "danger_zh", "danger_color",
            "danger_detail", "regime_loaded", "regime_light", "regime_zh",
            "regime_source",
        }, "ParallelVerdict 多/少了欄位 —— 若新增的是合併燈，先讀 §D1 硬約束"
        grid = {(b, k): parallel_verdict(b, "D", r)
                for b in _BANDS for k, r in _REGIMES.items()}
        for name in fields:
            if name == "note":
                continue
            half = "danger" if name.startswith("danger") else "regime"
            for fixed in (_BANDS if half == "danger" else _REGIMES):
                vals = {getattr(pv, name)
                        for (b, k), pv in grid.items()
                        if (b if half == "danger" else k) == fixed}
                assert len(vals) == 1, (
                    f"{name} 同時被兩邊決定（固定 {fixed} 仍有 {vals}）—— "
                    "這就是「調和成一個數字」")

    def test_overall_verdict_never_sees_the_regime(self):
        """危險度的**計算邏輯**不准動，也不准偷吃位階當輸入。"""
        node = _fn(_L5.read_text(encoding="utf-8"), "overall_verdict")
        assert [a.arg for a in node.args.args] == ["summary"]
        used = _names(node)
        for banned in ("get_macro_regime", "parallel_verdict", "regime",
                       "ParallelVerdict"):
            assert banned not in used, f"overall_verdict() 碰到了 {banned}"

    def test_the_l4_renderer_does_not_compare_anything(self):
        """L4 只印。它若自己再比一次色，畫面上就會有第二把尺。"""
        node = _fn(_L4.read_text(encoding="utf-8"), "render_regime_parallel")
        used = _names(node)
        for banned in ("BAND_META", "band_meta", "overall_verdict",
                       "BAND_LIGHT", "parallel_verdict"):
            assert banned not in used, f"render_regime_parallel() 碰到了 {banned}"


# ════════════════════════════════════════════════════════════════
# 四、位階未載入要誠實（§1：不留白、不拿危險度的燈冒充）
# ════════════════════════════════════════════════════════════════
class TestUnloadedHonesty:

    @pytest.mark.parametrize("band", _BANDS)
    def test_unloaded_regime_never_borrows_the_danger_light(self, band):
        from src.ui.tabs.tab_macro_v2 import parallel_verdict
        pv = parallel_verdict(band, "D", _REGIMES["unloaded"])
        assert pv.regime_loaded is False
        assert pv.regime_light == "⬜"
        assert pv.regime_zh == "未評估"

    def test_the_unloaded_note_tells_the_user_what_to_press(self):
        from src.ui.tabs.tab_macro_v2 import REGIME_UNLOADED_NOTE as N
        assert "尚未評估" in N and "一鍵更新" in N
        assert "不留白" in N

    def test_missing_fields_are_treated_as_unloaded_not_as_neutral(self):
        """§1：契約欄位缺了就是未評估，**不補任何預設多空**。"""
        from src.ui.tabs.tab_macro_v2 import parallel_verdict
        for reg in ({}, {"regime": "bull"}, {"is_loaded": False,
                                             "regime": "bull", "light": "🟢"}):
            pv = parallel_verdict("green", "D", reg)
            assert pv.regime_loaded is False
            assert pv.regime_zh == "未評估"

    def test_l4_prints_a_placeholder_not_a_blank(self):
        node = _fn(_L4.read_text(encoding="utf-8"), "render_regime_parallel")
        body = ast.unparse(node)
        assert "尚未評估" in body, "位階未載入時畫面會留白"
        assert "⬜" in body


# ════════════════════════════════════════════════════════════════
# 五、slow lane：真的把卡片渲染出來
# ════════════════════════════════════════════════════════════════
@pytest.mark.slow
class TestRuntimeCard:
    """headless mount：兩顆燈是不是真的同時出現在畫面上。

    上面幾節守的是「函式回了什麼」；這一節守「Streamlit 真的把它印出來了」。
    兩者都要 —— 純函式全綠而 `st.markdown` 少呼叫一次，畫面照樣沒東西。
    """

    @staticmethod
    def _run(tmp_path, warroom: str):
        import textwrap

        from streamlit.testing.v1 import AppTest
        script = tmp_path / "_mount_v2_parallel.py"
        script.write_text(textwrap.dedent(f"""
            import streamlit as st
            st.session_state['warroom_summary'] = {warroom}
            from src.ui.tabs.tab_macro_v2 import render_tab_macro_v2
            render_tab_macro_v2()
        """), encoding="utf-8")
        at = AppTest.from_file(str(script), default_timeout=120)
        at.run()
        assert not at.exception, f"總經 v2 mount 炸了: {at.exception}"
        return at

    def test_both_verdicts_are_on_screen(self, tmp_path):
        at = self._run(tmp_path, "{'health_score': 66.0, 'regime': 'bull', "
                                 "'market_score': 5, 'futures_net': 0}")
        blob = "\n".join(m.value for m in at.markdown)
        caps = "\n".join(c.value for c in at.caption)
        assert "指標危險度" in blob, "正名後的標題沒印出來"
        assert "總經位階" not in blob, "舊標題又出現在畫面上"
        assert "市場位階" in blob, "並列的另一半沒印出來"
        assert "多頭" in blob, "位階的中文結論沒印出來"
        assert "bull:score" in blob, "沒揭露位階是哪個分支生效"
        assert ("不是同一件事" in caps) or ("不代表它們是同一個判斷" in caps), \
            "沒有告訴使用者這兩個看的東西不一樣"

    @pytest.mark.skipif(
        pathlib.Path("macro_state.json").exists(),
        reason="本機有 AI 鎖定快照 → 位階會從 macro_state.json 載入，"
               "「未評估」這條分支在這台機器上打不到（該檔已 gitignore，CI 必然沒有）")
    def test_unloaded_regime_says_so_on_screen(self, tmp_path):
        """沒按過「一鍵更新」→ 畫面要明說位階尚未評估，不是留白。

        ⚠️ 這條依賴「`macro_state.json` 不存在」—— `get_macro_regime()` 在
        warroom 空時會退到那份 AI 鎖定快照。該檔 gitignore，CI 一定沒有；
        開發機上若有就 skip（不是讓它假裝通過）。
        """
        at = self._run(tmp_path, "{}")
        blob = "\n".join(m.value for m in at.markdown)
        caps = "\n".join(c.value for c in at.caption)
        assert "市場位階" in blob
        assert "尚未評估" in blob
        assert "一鍵更新" in caps
