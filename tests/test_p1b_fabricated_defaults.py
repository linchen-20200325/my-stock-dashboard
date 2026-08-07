"""P1-B 守衛：捏造預設值 + 殘餘「站上 20MA」謊言 + ^TNX 刻度（v19.177, 2026-08-06）。

三個獨立缺陷，共同的根因都是「讓程式不報錯」而不是「解決問題」（CLAUDE.md §1）。

① 捏造預設值（`macro_helpers.calc_traffic_light`）
   | 舊碼 | 問題 |
   |---|---|
   | `_jqavg = _jq.get('avg', 50)` | 以 **60% 權重**進健康評分；缺值時憑空製造「廣度中性」 |
   | `_leek = 50`                  | 該欄是**小台法人空多比**（±100%、中位 **0**）→ 50 是極端偏空，不是中性（§4.1） |
   | `_fut_net = 0`                | 讓 `_defense` 恆為假 ＝ 把「不知道」當成「沒有大空單」 |
   附帶破口：`_conf_sources` 用 `bool(jingqi_info)` 判在不在，而 `section_inputs`
   在 warroom 缺值時會合成 `{'avg': None}`（非空 dict → True）⇒ 缺失被吃掉；
   `handlers._render_traffic_light` 又只在 `conf < 70` 列缺項、`conf < 80` 印警告，
   而 5 源缺 1 源時 conf 正好 **80** ⇒ 兩個分支都進不去 ⇒ 降級**完全看不見**。

② 「旌旗指數＝站上 20MA 家數比」是捏造的資料描述（§1 反捏造）
   全站**沒有任何一行 code 在算「站上均線的股票家數比」**。真值 =
   上漲佔比（ad_ratio）的 5 日移動平均（`src/services/jingqi_calc.py:43`）。
   v19.176 已修 5 處；本版清掉剩下的 6 處複本（含 SSOT 模組自己的 docstring）。

③ `^TNX` 刻度：`reconcile.py` 文件寫「= 殖利率 × 10」寫死 ÷10，但實機是直接 %
   （4.63）⇒ 對帳面板 US10Y 那列永久紅（假紅）。改為**偵測刻度**，越界回 None。

守衛設計（避免假紅燈，本 session 已被字串掃描守衛的假紅擋過三輪）
================================================================
- 一律用 **AST** 而非 regex / naive substring：
  * 註解天生不在 AST 內 → 解釋「為何退役」的中文註解不會被誤殺。
  * docstring 另行以 `ast.get_docstring` 顯式排除（掃畫面字串時）；
    唯一例外是 `jingqi_calc` 的**模組 docstring 本身就是謊言源頭**，
    故對它另開一條專測。
- 允許**否定式澄清**（同一段字串內含「不是 / 並未 / 從未 / 沒有」）——
  誠實揭露「本系統沒有這個量」正是修法本身，不能被守衛擋掉。
- 失敗訊息一律印出 `檔名:行號` + **該行原始碼原文**，讓紅燈可以直接定位。
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent

_MACRO_HELPERS = "src/compute/macro/macro_helpers.py"
_HANDLERS = "src/ui/tabs/macro/handlers.py"
_CLASSROOM = "src/ui/tabs/macro_classroom.py"
_JINGQI = "src/services/jingqi_calc.py"
_RECONCILE = "src/compute/risk/reconcile.py"

#: 「站上均線的股票家數比」這個量**不存在於本專案**（與 test_p0c_breadth_naming
#: 的 `_FABRICATED_BREADTH_PHRASES` 同源，另補「站上年線」——tab_edu 用的是這個寫法）。
#: 刻意用連續片語而非關鍵字共現：教學頁有合法敘述「MA120 連三日站上/跌破 …
#: （廣度、漲跌家數是進市場分數）」，共現式比對會誤殺。
_FABRICATED_PHRASES = (
    "站上均線",
    "站在均線",
    "站上 20MA",
    "站上20MA",
    "站上年線",
)

#: 同一段文字內出現任一詞 → 視為「否定式澄清」，合法。
_NEGATIONS = ("不是", "並未", "從未", "沒有", "無任何", "不再", "不得")

#: 本版清掉複本的檔案（含畫面字串的）。jingqi_calc 的謊言在 module docstring，
#: 由 `TestJingqiDocstringTellsTruth` 另測。
_CLEANED_SCREEN_FILES = (
    _MACRO_HELPERS,
    "src/ui/tabs/macro/section_long.py",
    "src/ui/tabs/tab_macro.py",
    "shared/macro_buckets.py",
    "src/ui/tabs/tab_edu.py",
)


# ══════════════════════════════════════════════════════════════════
# AST 小工具（含「印出該行原文」的失敗訊息）
# ══════════════════════════════════════════════════════════════════
def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def _lines(rel: str) -> list[str]:
    return _src(rel).splitlines()


def _tree(rel: str) -> ast.Module:
    return ast.parse(_src(rel), filename=rel)


def _at(rel: str, lineno: int) -> str:
    """`檔名:行號: <該行原始碼原文>` —— 守衛失敗時直接可定位。"""
    _ls = _lines(rel)
    _txt = _ls[lineno - 1].strip() if 0 < lineno <= len(_ls) else "<行號超出檔案範圍>"
    return f"{rel}:{lineno}: {_txt}"


def _func(rel: str, name: str) -> ast.FunctionDef:
    for node in ast.walk(_tree(rel)):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{rel} 找不到函式 {name}（是否被改名／刪除？守衛失效）")


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """所有 docstring 的 Constant 節點 id（掃畫面字串時排除）。"""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                out.add(id(first.value))
    return out


def _screen_strings(rel: str) -> list[tuple[int, str]]:
    """檔內所有**可能被渲染到畫面**的字串字面值 → [(lineno, value)]。"""
    tree = _tree(rel)
    skip = _docstring_node_ids(tree)
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and id(n) not in skip]


def _numeric_const(node: ast.AST) -> float | None:
    """數值字面值（含 `-3` 這種 UnaryOp）→ float；否則 None。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _numeric_const(node.operand)
        if inner is not None:
            return -inner if isinstance(node.op, ast.USub) else inner
    return None


def _get_calls_with_numeric_default(node: ast.AST) -> list[tuple[int, str, float]]:
    """找 `<x>.get(<key>, <數字>)` → [(lineno, key, default)]。

    這是本次三個捏造預設值的共同寫法之一（另一種是直接 `_leek = 50`）。
    ⚠️ `dict.get` 的預設值**只在 key 不存在時生效** —— 上游明確寫入 None 時
    根本不會生效，所以它既捏造又不可靠，兩頭都不對。
    """
    out: list[tuple[int, str, float]] = []
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        if not (isinstance(n.func, ast.Attribute) and n.func.attr == "get"):
            continue
        if len(n.args) < 2:
            continue
        key = n.args[0].value if isinstance(n.args[0], ast.Constant) else "<non-const>"
        dflt = _numeric_const(n.args[1])
        if dflt is not None:
            out.append((n.lineno, str(key), dflt))
    return out


# ══════════════════════════════════════════════════════════════════
# ① 捏造預設值 —— 原始碼守衛
# ══════════════════════════════════════════════════════════════════
_BANNED_NUMERIC_DEFAULT_KEYS = ("avg", "韭菜指數", "外資大小", "fut_net", "leek")


class TestNoFabricatedDefaultsInSource:
    def test_calc_traffic_light_has_no_numeric_get_default(self):
        """`calc_traffic_light` 內不得再有 `.get('avg'|'韭菜指數'|'外資大小', <數字>)`。"""
        fn = _func(_MACRO_HELPERS, "calc_traffic_light")
        offenders = [
            _at(_MACRO_HELPERS, ln) + f"   ← key={k!r} 捏造預設 {d:g}"
            for ln, k, d in _get_calls_with_numeric_default(fn)
            if k in _BANNED_NUMERIC_DEFAULT_KEYS
        ]
        assert not offenders, (
            "calc_traffic_light 又出現捏造的數值預設（§1 禁止「自行估一個合理值」）：\n"
            + "\n".join(offenders)
            + "\n\n缺值請一律用 None，並確認 `_conf_sources` 會把它列進 missing_sources。"
        )

    @pytest.mark.parametrize("var", ["_leek", "_fut_net", "_jqavg"])
    def test_no_numeric_literal_initialisation(self, var: str):
        """`_leek = 50` / `_fut_net = 0` / `_jqavg = 50` 這種字面值初始化一律違憲。"""
        fn = _func(_MACRO_HELPERS, "calc_traffic_light")
        offenders = []
        for n in ast.walk(fn):
            if not isinstance(n, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == var for t in n.targets):
                continue
            num = _numeric_const(n.value)
            if num is not None:
                offenders.append(_at(_MACRO_HELPERS, n.lineno)
                                 + f"   ← {var} 被塞字面值 {num:g}")
        assert not offenders, (
            f"{var} 被以數值字面值初始化（§1 Fail Loud）：\n" + "\n".join(offenders)
            + f"\n\n{var} 缺值時必須是 None —— 尤其 _leek："
            "該欄是小台法人空多比（±100%、中位 0），50 在此尺度上是極端值不是中性（§4.1）。"
        )

    @pytest.mark.parametrize("bad_fut", [None, float("nan"), "", "N/A"])
    def test_defense_guards_missing_fut_net(self, bad_fut):
        """外資期貨淨口缺值時：**不觸發防禦、也不得拋例外**。

        ── C1 v19.182 守衛改寫（從字面掃描 → 行為斷言）──────────────────
        原本這條是 AST 掃 `calc_traffic_light` 裡 `_defense = ...` 那一行的
        `ast.unparse` 字串是否含 `"_fut_net is not None"`。兩個問題：

        1. **它只是照抄實作的字面**。實作寫什麼、守衛就要求什麼，所以它
           **永遠不可能發現實作本身是錯的** —— 只要有人把判斷式改成
           `_fut_net is not None and False`，守衛照樣綠燈。
        2. 判定邏輯 C1 已下沉至 L0 `shared.regime_arbiter`（全站唯一仲裁點），
           caller 端只剩 `_defense = _verdict.defense`。字面掃描看不到它，
           會產出**假紅燈**，而 §1 想守的性質（缺值不被當成安全訊號、
           `abs(None)` 不炸）其實沒有變。

        改為直接對 `is_foreign_futures_defense()` 餵四種「缺值」表示法，
        斷言回 False 且不拋 —— 這才會在實作真的退化時變紅。
        （「有大空單時仍照常觸發」的反向護欄見
        `TestDefenseNotTriggeredByMissingData::test_real_big_short_still_triggers_defense`
        與本類的 `test_known_big_short_still_defends`，兩條方向相反、互不矛盾。）
        """
        from shared.regime_arbiter import is_foreign_futures_defense
        assert is_foreign_futures_defense(market_score=1, futures_net_lots=bad_fut) is False

    def test_known_big_short_still_defends(self):
        """反向護欄：已知的大額淨空單仍必須觸發防禦（門檻 SSOT 30,000 口）。

        與上一條方向相反但**不互斥** —— 上一條講「缺值」，這條講「已知且超標」。
        """
        from shared.regime_arbiter import is_foreign_futures_defense
        assert is_foreign_futures_defense(market_score=1, futures_net_lots=-40000) is True

    def test_defense_delegates_to_single_arbiter(self):
        """`calc_traffic_light` 不得再自行重寫防禦判定式（§2.1 SSOT）。

        這條**不是**字面抄襲守衛：它要求的是「本函式裡沒有第二份實作」，
        而不是「這一行長得像某個樣子」。判定式若被複製回來，`_defense` 的
        右手邊就會重新出現 `FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD` 比較。
        """
        fn = _func(_MACRO_HELPERS, "calc_traffic_light")
        offenders = []
        for n in ast.walk(fn):
            if not isinstance(n, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "_defense" for t in n.targets):
                continue
            seg = ast.unparse(n.value)
            if "FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD" in seg:
                offenders.append(_at(_MACRO_HELPERS, n.lineno) + f"\n       {seg}")
        assert not offenders, (
            "`_defense` 在 calc_traffic_light 內被重新實作（應改吃 "
            "`shared.regime_arbiter.arbitrate_regime()` 的 verdict）：\n"
            + "\n".join(offenders)
        )


# ══════════════════════════════════════════════════════════════════
# ① 捏造預設值 —— 行為
# ══════════════════════════════════════════════════════════════════
_MKT_OK = {"score": 3, "max_score": 4, "regime": "neutral"}
_CL_OK = {"inst": {"外資自營": {"net": 100}}, "adl": 1}


def _tl(mkt=None, jq=None, cl=None, li=None):
    from src.compute.macro import calc_traffic_light
    return calc_traffic_light(
        _MKT_OK if mkt is None else mkt,
        jq, _CL_OK if cl is None else cl, li,
    )


class TestMissingInputsStayNone:
    def test_jqavg_none_when_jingqi_info_absent(self):
        tl = _tl(jq=None)
        assert tl["jqavg"] is None, "旌旗缺值仍被捏成數字"
        assert tl["health_partial"] is True

    def test_jqavg_none_when_synthesised_dict_carries_none(self):
        """`section_inputs` 在 warroom 缺 jingqi_avg 時合成 `{'avg': None}`。

        這是舊碼**最陰**的一條路：dict 非空 → `bool(jingqi_info)` 為 True →
        conf 不降、缺項不列；但 `.get('avg', 50)` 的預設又因為 key 存在而不生效
        → 拿到 None → 舊碼下一行乘法直接 TypeError。
        """
        tl = _tl(jq={"avg": None})
        assert tl["jqavg"] is None
        assert tl["health_partial"] is True
        assert any("旌旗" in m for m in tl["missing_sources"]), (
            f"合成的 {{'avg': None}} 未被列入缺失來源：{tl['missing_sources']}")

    def test_leek_and_fut_net_none_without_li(self):
        tl = _tl(jq={"avg": 60}, li=None)
        assert tl["leek"] is None
        assert tl["fut_net"] is None

    def test_leek_and_fut_net_none_when_columns_missing(self):
        li = pd.DataFrame({"其他欄": [1]})
        tl = _tl(jq={"avg": 60}, li=li)
        assert tl["leek"] is None
        assert tl["fut_net"] is None

    def test_nan_cell_is_treated_as_missing_not_zero(self):
        """易錯輸入 ①：欄位在但值是 NaN（leading_indicators 對沒抓到的日子會塞 NaN）。

        舊碼 `float(nan)` **不會**拋例外 → NaN 一路流進 `abs(_fut_net) > 30000`
        （NaN 比較恆 False，靜默失效）與 warroom；`float(None)` 才拋例外並悄悄
        退回捏造值。兩條路都不誠實。
        """
        li = pd.DataFrame({"外資大小": [float("nan")], "韭菜指數": [float("nan")]})
        tl = _tl(jq={"avg": 60}, li=li)
        assert tl["fut_net"] is None, "NaN 應視為缺值，不可流進判定"
        assert tl["leek"] is None

    def test_none_cell_is_treated_as_missing(self):
        li = pd.DataFrame({"外資大小": [None], "韭菜指數": [None]})
        tl = _tl(jq={"avg": 60}, li=li)
        assert tl["fut_net"] is None
        assert tl["leek"] is None

    def test_real_values_still_pass_through(self):
        li = pd.DataFrame({"外資大小": [-87455], "韭菜指數": [34.7]})
        tl = _tl(jq={"avg": 53}, li=li)
        assert tl["fut_net"] == pytest.approx(-87455.0)
        assert tl["leek"] == pytest.approx(34.7)
        assert tl["jqavg"] == pytest.approx(53.0)


class TestDefenseNotTriggeredByMissingData:
    def test_missing_fut_net_does_not_trigger_defense(self):
        """缺資料**不觸發**防禦（也不該假裝安全）。"""
        tl = _tl(mkt={"score": 0, "max_score": 4, "regime": "bull"},
                 jq={"avg": 60}, li=None)
        assert tl["defense"] is False
        assert tl["fut_net"] is None

    def test_real_big_short_still_triggers_defense(self):
        """回歸：真的有大空單時防禦照常觸發（門檻 SSOT 30000 口）。"""
        li = pd.DataFrame({"外資大小": [-87455], "韭菜指數": [34.7]})
        tl = _tl(mkt={"score": 1, "max_score": 4, "regime": "bull"},
                 jq={"avg": 60}, li=li)
        assert tl["defense"] is True


class TestHealthRenormalisesInsteadOfFabricating:
    def test_full_inputs_identical_to_legacy_formula(self):
        """零回歸：兩項都在時 Σw = 1.0，歸一化後與舊公式逐位相同。"""
        from shared.signal_thresholds import HEALTH_WEIGHT_JQ, HEALTH_WEIGHT_SCORE
        tl = _tl(mkt={"score": 3, "max_score": 4, "regime": "neutral"},
                 jq={"avg": 53})
        legacy = round(53 * HEALTH_WEIGHT_JQ + (3 / 4 * 100) * HEALTH_WEIGHT_SCORE, 1)
        assert tl["health"] == pytest.approx(legacy)
        assert tl["health_partial"] is False

    def test_missing_jqavg_uses_renormalised_weight_not_neutral_50(self):
        """缺旌旗 → health = 大盤評分分項本身（權重歸一化），**不是**「塞 50」。"""
        tl = _tl(mkt={"score": 3, "max_score": 4, "regime": "neutral"}, jq=None)
        assert tl["health"] == pytest.approx(75.0)      # (3/4*100) 權重歸一化後
        # 舊行為（捏 50）會是 50*0.6 + 75*0.4 = 60.0 —— 明確釘住兩者不同
        assert not math.isclose(tl["health"], 60.0, abs_tol=1e-9)
        assert tl["health_partial"] is True

    def test_weights_sum_to_one_so_no_silent_rescale(self):
        """§4.2：權重和 = 1，歸一化在滿輸入時必須是 no-op。"""
        from shared.signal_thresholds import HEALTH_WEIGHT_JQ, HEALTH_WEIGHT_SCORE
        assert math.isclose(HEALTH_WEIGHT_JQ + HEALTH_WEIGHT_SCORE, 1.0, abs_tol=1e-12)


class TestConfidenceRealSourceDetection:
    def test_conf_drops_when_jqavg_missing(self):
        """易錯輸入 ②：jingqi_info 是**非空 dict 但 avg 為 None**。

        舊碼 `bool(jingqi_info)` → True → conf 不降（100%），缺失完全隱形。
        """
        tl = _tl(jq={"avg": None},
                 li=pd.DataFrame({"外資大小": [1], "韭菜指數": [1]}))
        assert tl["conf"] == 80, f"conf 未因旌旗缺值下降：{tl['conf']}"
        assert len(tl["missing_sources"]) == 1

    def test_conf_full_when_everything_present(self):
        tl = _tl(jq={"avg": 60},
                 li=pd.DataFrame({"外資大小": [1], "韭菜指數": [1]}))
        assert tl["conf"] == 100
        assert tl["missing_sources"] == []

    def test_conf_label_matches_breadth_ssot(self):
        """L2 寫的字面值必須與 L4 名詞 SSOT 對得上（L2 不得上行 import，§8.2）。"""
        from src.compute.macro.macro_helpers import _CONF_LABEL_JINGQI
        from src.ui.render.ui_widgets import BREADTH_JINGQI, BREADTH_UP_RATIO
        assert BREADTH_JINGQI.canonical in _CONF_LABEL_JINGQI, (
            f"信心來源標籤未用旌旗正式名：{_CONF_LABEL_JINGQI!r}")
        assert BREADTH_UP_RATIO.canonical in _CONF_LABEL_JINGQI, (
            f"標籤未說明它由「上漲佔比」推導：{_CONF_LABEL_JINGQI!r}")
        assert "5 日" in _CONF_LABEL_JINGQI, (
            f"標籤未標明 5 日均（口徑差異，§4.1）：{_CONF_LABEL_JINGQI!r}")
        assert not any(p in _CONF_LABEL_JINGQI for p in _FABRICATED_PHRASES), (
            f"信心來源標籤又寫回捏造描述：{_CONF_LABEL_JINGQI!r}")


# ══════════════════════════════════════════════════════════════════
# ① 降級必須在畫面上看得見 —— handlers / macro_classroom
# ══════════════════════════════════════════════════════════════════
class TestDegradationIsVisibleOnScreen:
    def test_no_conf_lt_80_gate_left(self):
        """`conf < 80` 是壞條件：5 源缺 1 源時 conf 正好 80 ⇒ 什麼都不顯示。"""
        fn = _func(_HANDLERS, "_render_traffic_light")
        offenders = []
        for n in ast.walk(fn):
            if not isinstance(n, ast.Compare):
                continue
            seg = ast.unparse(n)
            if "conf" not in seg:
                continue
            operands = [n.left, *n.comparators]
            if any(_numeric_const(o) == 80.0 for o in operands):
                offenders.append(_at(_HANDLERS, n.lineno) + f"   ← 條件：{seg}")
        assert not offenders, (
            "`conf` 與 80 比較的條件又出現了 —— 缺 1/5 項時 conf == 80，"
            "`80 < 80` 為 False ⇒ 降級在畫面上完全看不到：\n"
            + "\n".join(offenders)
            + "\n\n請改成「只要 missing_sources 非空就逐項列出」。"
        )

    def test_missing_sources_rendered_outside_the_conf70_block(self):
        """`missing_sources` 至少要被讀兩次：conf<70 擋燈分支 + 正常燈號下的揭露。"""
        fn = _func(_HANDLERS, "_render_traffic_light")
        hits = [n.lineno for n in ast.walk(fn)
                if isinstance(n, ast.Constant) and n.value == "missing_sources"]
        assert len(hits) >= 2, (
            "`missing_sources` 在 `_render_traffic_light` 內只被讀 "
            f"{len(hits)} 次（行號 {hits}）—— 表示只有 conf<70 的擋燈分支會列缺項，"
            "conf ∈ [70,100) 的降級又變回隱形（§1 降級必須可見）。"
        )

    def test_health_partial_flag_is_surfaced(self):
        """健康評分只剩一條腿時，畫面必須講出來（權重 60% 的分項不見了）。"""
        hits = [n.lineno for n in ast.walk(_tree(_HANDLERS))
                if isinstance(n, ast.Constant) and n.value == "health_partial"]
        assert hits, (
            f"{_HANDLERS} 沒有讀 `health_partial` —— 旌旗缺席時使用者看到的"
            "『綜合健康度』與平常量級意義不同，卻毫無提示（§1）。")

    def test_classroom_does_not_reintroduce_numeric_default_for_fut_net(self):
        """`tl.get('fut_net', 0)` 會在 key 存在且值為 None 時回 None → 格式化炸掉。"""
        offenders = [
            _at(_CLASSROOM, ln) + f"   ← key={k!r} 捏造預設 {d:g}"
            for ln, k, d in _get_calls_with_numeric_default(_tree(_CLASSROOM))
            if k in ("fut_net", "leek", "jqavg")
        ]
        assert not offenders, (
            "紅綠燈判讀說明又用數值預設接 tl 欄位：\n" + "\n".join(offenders)
            + "\n\n這些欄位 v19.177 起可能是 None；`.get(k, 0)` 的預設只在 key 不存在時"
              "生效，接到 None 後 f-string 的 `:+,.0f` 會 TypeError，"
              "而 caller（section_state.py:501）的 try/except 會把整個 expander 吞掉。"
        )

    def test_classroom_renders_without_crash_when_fut_net_is_none(self):
        """行為面：tl 帶 None 欄位時，判讀說明不得拋例外（用 stub streamlit）。"""
        pytest.importorskip("streamlit")
        import src.ui.tabs.macro_classroom as mc

        class _Stub:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def markdown(self, *a, **k):
                return None

            def expander(self, *a, **k):
                return self

            # v19.185 D2:explainer 改成同時揭露「趨勢面 regime(輸入)」與
            # 「生效 regime(結論)」後會呼叫 st.caption / st.warning / st.info。
            # 這個 stub 只實作 markdown+expander,於是本測試以 AttributeError 紅燈
            # —— 但它要測的是「fut_net=None 不得崩潰」,不是「只准用 markdown」。
            # 補齊常見的無回傳 render API,避免 stub 的覆蓋面變成隱性契約。
            def caption(self, *a, **k):
                return None

            def warning(self, *a, **k):
                return None

            def info(self, *a, **k):
                return None

            def write(self, *a, **k):
                return None

        _orig = mc.st
        mc.st = _Stub()
        try:
            mc.render_traffic_light_explainer({
                "color": "#fff", "label": "x", "health": 40.0, "score": 1,
                "regime": "neutral", "defense": False, "fut_net": None, "conf": 80,
            })
        finally:
            mc.st = _orig


# ══════════════════════════════════════════════════════════════════
# ② 「站上 20MA」謊言的殘餘複本
# ══════════════════════════════════════════════════════════════════
class TestNoFabricatedMaBreadthLeftOnScreen:
    @pytest.mark.parametrize("rel", _CLEANED_SCREEN_FILES)
    def test_screen_strings_clean(self, rel: str):
        """畫面字串不得再宣稱「站上均線／年線家數比」（允許否定式澄清）。"""
        offenders = [
            _at(rel, ln) + f"\n       字串：{val!r}"
            for ln, val in _screen_strings(rel)
            if any(p in val for p in _FABRICATED_PHRASES)
            and not any(neg in val for neg in _NEGATIONS)
        ]
        assert not offenders, (
            f"{rel} 仍在畫面字串宣稱本系統沒有的量（§1 反捏造）：\n"
            + "\n".join(offenders)
            + "\n\n真值：旌旗指數 = 上漲佔比的 5 日均"
              "（src/services/jingqi_calc.py:43；名詞 SSOT ui_widgets.BREADTH_JINGQI）。"
        )


class TestJingqiDocstringTellsTruth:
    """SSOT 模組自己的檔頭 —— 這裡是謊言的源頭，其他 5 處都是從這抄的。"""

    def test_module_docstring_states_five_day_mean(self):
        doc = ast.get_docstring(_tree(_JINGQI)) or ""
        assert doc, f"{_JINGQI} 沒有 module docstring"
        assert "5 日" in doc, (
            f"{_JINGQI} 的 docstring 未寫出真定義（上漲佔比的 5 日均）：\n{doc[:400]}")
        assert "ad_ratio" in doc, f"{_JINGQI} 的 docstring 未指回實際欄位 ad_ratio"

    def test_module_docstring_only_mentions_ma_breadth_as_negation(self):
        doc = ast.get_docstring(_tree(_JINGQI)) or ""
        for para in doc.split("\n\n"):
            if any(p in para for p in _FABRICATED_PHRASES):
                assert any(neg in para for neg in _NEGATIONS), (
                    f"{_JINGQI} docstring 仍把「站上均線」當定義在寫（§1 反捏造）：\n"
                    f"{para}")

    def test_formula_line_still_the_evidence(self):
        """釘住 evidence：改實作就必須同時改文件（否則守衛失效而不自知）。"""
        src = _src(_JINGQI)
        assert "['ad_ratio'].tail(5).mean()" in src, (
            f"{_JINGQI} 的旌旗算式已變，但 docstring / 名詞 SSOT 可能沒跟著改 —— "
            "請同步更新 ui_widgets.BREADTH_JINGQI.formula 與各處文案。")


class TestBucketSpecLabelTellsTruth:
    def test_jingqi_spec_label_and_source(self):
        from shared.macro_buckets import SPECS_BY_KEY
        spec = SPECS_BY_KEY["jingqi"]
        for field in ("label", "source"):
            val = getattr(spec, field)
            assert not any(p in val for p in _FABRICATED_PHRASES), (
                f"DangerSpec('jingqi').{field} 仍是捏造描述：{val!r}")
        assert "上漲佔比" in spec.label, f"label 未寫真值：{spec.label!r}"

    def test_jingqi_thresholds_unchanged(self):
        """只改名字不改行為：門檻與方向必須原封不動（改門檻需另案校準）。"""
        from shared.macro_buckets import SPECS_BY_KEY
        spec = SPECS_BY_KEY["jingqi"]
        assert spec.yellow == pytest.approx(60.0)
        assert spec.red == pytest.approx(40.0)
        assert spec.direction == "low_bad"
        assert spec.bucket == "chips"
        assert spec.unit == "%"

    def test_health_note_no_longer_repeats_the_lie(self):
        """health 的因子揭露 note 也抄了同一句謊，一併釘住。"""
        from shared.macro_buckets import SPECS_BY_KEY
        note = SPECS_BY_KEY["health"].note
        assert not any(p in note for p in _FABRICATED_PHRASES), (
            f"health note 仍含捏造描述：{note!r}")
        # v19.173 既有守衛的內容不得被本次改動擠掉
        assert "旌旗" in note and "60%" in note and "不含" in note


# ══════════════════════════════════════════════════════════════════
# ③ ^TNX 刻度偵測
# ══════════════════════════════════════════════════════════════════
class TestNormalizeTnxQuote:
    @pytest.mark.parametrize("raw,expect", [
        (4.63, 4.63),      # 實機慣例：直接 %
        (0.0, 0.0),        # 下邊界
        (20.0, 20.0),      # 直接 % 上邊界（含）
        (20.0001, 2.00001),   # 越過即判 ×10
        (42.5, 4.25),      # 舊測試沿用的 ×10 慣例
        (46.3, 4.63),      # 同一天的 ×10 版
        (200.0, 20.0),     # ×10 上邊界（含）
    ])
    def test_scale_detection(self, raw, expect):
        from src.compute.risk.reconcile import normalize_tnx_quote
        val, src = normalize_tnx_quote(raw)
        assert val == pytest.approx(expect), f"{raw} → {val}（期望 {expect}）｜{src}"
        assert src.startswith("Yahoo:^TNX"), src

    @pytest.mark.parametrize("raw", [200.1, 1000.0, -0.01, -5.0])
    def test_out_of_both_ranges_returns_none(self, raw):
        """易錯輸入 ③：兩種慣例都解釋不通 → 回 None + log，**不猜換算**（§1）。"""
        from src.compute.risk.reconcile import normalize_tnx_quote
        val, src = normalize_tnx_quote(raw)
        assert val is None, f"{raw} 被硬湊成 {val}（應誠實回 None）"
        assert "越界" in src, src

    @pytest.mark.parametrize("raw", [None, float("nan"), "abc", object()])
    def test_non_numeric_returns_none(self, raw):
        from src.compute.risk.reconcile import normalize_tnx_quote
        val, _src = normalize_tnx_quote(raw)
        assert val is None

    def test_labels_disclose_detected_convention(self):
        from src.compute.risk.reconcile import normalize_tnx_quote
        assert "直接%" in normalize_tnx_quote(4.63)[1]
        assert "×10" in normalize_tnx_quote(46.3)[1]

    def test_ranges_align_with_claude_md_3_2(self):
        """合理範圍取自 CLAUDE.md §3.2「US10Y (%) [0, 20]」，非腦補。"""
        from src.compute.risk import reconcile as R
        assert R.TNX_DIRECT_PCT_MIN == pytest.approx(0.0)
        assert R.TNX_DIRECT_PCT_MAX == pytest.approx(20.0)
        assert R.TNX_X10_MAX == pytest.approx(R.TNX_DIRECT_PCT_MAX * 10.0)
        # 與五桶守衛同源（同一條 §3.2 規則不得兩處各寫一個數字）
        from shared.macro_buckets import SPECS_BY_KEY
        assert SPECS_BY_KEY["us10y"].valid_max == pytest.approx(R.TNX_DIRECT_PCT_MAX)
        assert SPECS_BY_KEY["us10y"].valid_min == pytest.approx(R.TNX_DIRECT_PCT_MIN)


class TestReconcileUs10yScaleRegression:
    def test_live_direct_pct_no_longer_false_red(self):
        """實機回歸：FRED 4.63 vs Yahoo 4.63（直接 %）必須 agree，不再永久紅。"""
        from src.compute.risk.reconcile import reconcile_us10y_yield
        r = reconcile_us10y_yield(4.63, 4.63)
        assert r["status"] == "agree", r
        assert r["value_b"] == pytest.approx(4.63)

    def test_legacy_x10_convention_still_agrees(self):
        """向後相容：舊 ×10 慣例（42.5）照樣對得起來。"""
        from src.compute.risk.reconcile import reconcile_us10y_yield
        r = reconcile_us10y_yield(4.25, 42.5)
        assert r["status"] == "agree"
        assert r["value_b"] == pytest.approx(4.25)

    def test_real_divergence_still_disagrees(self):
        """守住對帳本職：真的差 48bp 就要紅。"""
        from src.compute.risk.reconcile import reconcile_us10y_yield
        r = reconcile_us10y_yield(4.52, 50.0)
        assert r["status"] == "disagree"

    def test_out_of_range_quote_is_missing_not_disagree(self):
        """刻度不明 → ⬜ b_missing（誠實未知），不是 🔴 disagree（假紅）。"""
        from src.compute.risk.reconcile import reconcile_us10y_yield
        r = reconcile_us10y_yield(4.63, 463.0)
        assert r["status"] == "b_missing", r

    def test_source_b_is_dynamic_not_hardcoded_over_ten(self):
        """`source_b` 必須回報偵測結果，不得再寫死 'Yahoo:^TNX/10'。"""
        from src.compute.risk.reconcile import reconcile_us10y_yield
        assert reconcile_us10y_yield(4.63, 4.63)["source_b"] != "Yahoo:^TNX/10"

    def test_no_bare_div_ten_left_in_function(self):
        """原始碼守衛：`reconcile_us10y_yield` 內不得再有裸 `/ 10` 硬換算。"""
        fn = _func(_RECONCILE, "reconcile_us10y_yield")
        offenders = []
        for n in ast.walk(fn):
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) \
                    and _numeric_const(n.right) == 10.0:
                offenders.append(_at(_RECONCILE, n.lineno) + f"   ← {ast.unparse(n)}")
        assert not offenders, (
            "`reconcile_us10y_yield` 又寫死 ÷10（實機是直接 % ⇒ 對帳永久假紅）：\n"
            + "\n".join(offenders)
            + "\n\n請走 normalize_tnx_quote()：偵測刻度、越界回 None，不猜換算（§1）。"
        )


class TestReconcilePanelDoesNotFabricateFnet:
    def test_fnet_none_when_inst_absent(self):
        """`_get_health_params` 不得再把缺席的外資 net 捏成 0。

        v2（min_of_factors）在 `fnet <= 0` 時會加一個 40 分壓制項 ⇒ 捏 0 會讓
        「三大法人沒載入」被當成「外資淨賣」，該列變假紅。
        """
        pytest.importorskip("streamlit")
        from src.ui.pages import reconcile_panel as P
        _state: dict = {}
        _orig = P._ss
        P._ss = lambda k, d=None: _state.get(k, d)   # type: ignore[assignment]
        try:
            _jq, _sc, _fn = P._get_health_params()
        finally:
            P._ss = _orig   # type: ignore[assignment]
        assert _fn is None, f"外資 net 缺席卻回 {_fn!r}（§1 不得捏 0）"

    def test_no_numeric_default_for_net(self):
        fn = _func("src/ui/pages/reconcile_panel.py", "_get_health_params")
        offenders = [
            _at("src/ui/pages/reconcile_panel.py", ln) + f"   ← key={k!r} 預設 {d:g}"
            for ln, k, d in _get_calls_with_numeric_default(fn)
            if k in ("net", "jingqi_avg", "avg", "score")
        ]
        assert not offenders, (
            "健康評分對帳的輸入又被捏了預設值：\n" + "\n".join(offenders))
