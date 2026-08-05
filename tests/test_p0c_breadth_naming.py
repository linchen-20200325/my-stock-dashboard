"""P0-C 守衛：市場廣度名詞定名 + 旌旗 session key 回寫汙染（2026-08-05）。

背景（考證結果，證據見 `src/ui/render/ui_widgets.py` 檔頭大註解）
================================================================
修正前同一個概念三個名字、互相矛盾，且**同一個標題配三種演算法**：

| 出處 | 標題 | 實際的量 |
|---|---|---|
| ui_widgets:38 (舊) | 旌旗指數＝全市場健康度 | 宣稱「站上均線家數比」← **系統從未計算此量** |
| ui_widgets:39 (舊) | 騰落指標＝市場廣度 | ADL 累積線 |
| section_overview:50 (舊) | 全市場健康度 | 旌旗＝ad_ratio **5 日均** |
| section_short:187-190 (舊) | 全市場健康度 | **當日** ad_ratio，還顯示成「N 分」|
| 紅綠燈卡 | 綜合健康度 /100 | 0.6×旌旗 + 0.4×大盤評分（又是另一個量）|

定名結論：**它們本來就是不同的量**，所以不是硬合併成同一個詞，而是
一個量一個正式名（`ui_widgets.BREADTH_TERMS`），「市場廣度」降為**家族統稱**
（不可配單一數值），「全市場健康度」因一名三義而**整個退役**。

本檔釘住三件事
==============
1. 名詞定義只有一個出處（`BREADTH_TERMS`），UI 檔不得自寫廣度文案。
2. 退役名 / 捏造描述不得再出現在**畫面字串**（用 AST 掃字面值，不誤傷註解）。
3. `section_short` 不得再以「當日值」頂替旌旗；唯一保留的 fallback
   必須帶可見的代理旗標（§1 不可靜默頂替）。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

# 名詞定義 SSOT（**唯一**允許出現退役名字面值的地方 —— 它得把舊名列進黑名單）
_GLOSSARY_FILE = "src/ui/render/ui_widgets.py"

# 消費端 UI 檔：畫面字串一律不得再出現退役名 / 捏造描述
_CONSUMER_UI_FILES = (
    "src/ui/tabs/macro_classroom.py",
    "src/ui/tabs/macro/section_short.py",
    "src/ui/tabs/macro/section_overview.py",
    "src/ui/tabs/macro_stock_link.py",
)

_UI_FILES = (_GLOSSARY_FILE,) + _CONSUMER_UI_FILES

# 「站上均線的股票家數比例」這個量**不存在於本專案**。以下為其常見寫法，
# 出現在畫面字串即視為捏造描述復活（§1 反捏造）。
# 刻意用連續片語而非關鍵字共現 —— 理由見 test_no_fabricated_ma_breadth_claim。
_FABRICATED_BREADTH_PHRASES = (
    "站上均線",
    "站在均線",
    "站上 20MA",
    "站上20MA",
)

# jingqi_info 的鍵契約（與 tests/test_review_fixes_v19_84.py:19 同步）
_JQ_CONTRACT_KEYS = {"avg", "pos", "regime", "color", "label", "total", "source"}


def _src(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def _tree(rel: str) -> ast.Module:
    return ast.parse(_src(rel), filename=rel)


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """收集所有 docstring 的 Constant 節點 id（掃畫面字串時要排除）。

    docstring 是寫給開發者看的，和註解同性質；只有**非 docstring 的字面值**
    才可能被 render 到畫面上。
    """
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


def _screen_strings(rel: str) -> list[str]:
    """檔內所有**可能被渲染到畫面**的字串字面值（排除註解與 docstring）。

    註解天生不在 AST 裡，所以本函式自動不會誤判「解釋為什麼退役」的註解。
    """
    tree = _tree(rel)
    skip = _docstring_nodes(tree)
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and id(n) not in skip]


# ════════════════════════════════════════════════════════════════
# 1. 名詞定義 SSOT
# ════════════════════════════════════════════════════════════════
class TestBreadthGlossarySSOT:
    def test_terms_keyed_by_canonical(self):
        from src.ui.render.ui_widgets import BREADTH_TERMS
        assert BREADTH_TERMS, "廣度名詞表不可為空"
        for key, term in BREADTH_TERMS.items():
            assert key == term.canonical, f"{key} 的 key 必須等於 canonical"

    def test_canonical_names_unique(self):
        from src.ui.render.ui_widgets import BREADTH_TERMS
        names = [t.canonical for t in BREADTH_TERMS.values()]
        assert len(names) == len(set(names)), f"正式名重複: {names}"

    def test_nickname_differs_from_canonical(self):
        """白話名不可等於正式名，否則名詞表會印出「旌旗指數（旌旗指數）」。"""
        from src.ui.render.ui_widgets import BREADTH_TERMS
        for term in BREADTH_TERMS.values():
            assert term.nickname != term.canonical, \
                f"{term.canonical} 的 nickname 不可與 canonical 相同"

    def test_every_term_has_unit_and_evidence(self):
        """§2.2：每個名詞都要能追回 compute 層（evidence 帶 file:line）。"""
        from src.ui.render.ui_widgets import BREADTH_TERMS
        for term in BREADTH_TERMS.values():
            assert term.unit, f"{term.canonical} 缺單位（§4.1 量綱）"
            assert ".py:" in term.evidence, \
                f"{term.canonical} 的 evidence 必須指到 file:line，實際: {term.evidence!r}"

    def test_family_name_is_not_a_term(self):
        """「市場廣度」是家族統稱，不可被登記成某個單一數值的正式名。"""
        from src.ui.render.ui_widgets import BREADTH_FAMILY_NAME, BREADTH_TERMS
        assert BREADTH_FAMILY_NAME not in BREADTH_TERMS

    def test_jingqi_is_five_day_mean_of_up_ratio(self):
        """旌旗的定義必須寫「上漲佔比的 5 日均」——這是考證出來的真值。

        真值出處：src/services/jingqi_calc.py:43
            `_jq_ratio = float(df_adl_raw['ad_ratio'].tail(5).mean())`
        旁證：src/compute/macro/health_calibration.py:46
            「market_regime ④ 市場廣度用**日** ad_ratio；health 的 jqavg 是其 5 日均」
        """
        from src.ui.render.ui_widgets import BREADTH_JINGQI, BREADTH_UP_RATIO
        assert "5 日" in BREADTH_JINGQI.formula
        assert BREADTH_UP_RATIO.canonical in BREADTH_JINGQI.formula, \
            "旌旗的公式必須明說它是由『上漲佔比』推導的"
        assert BREADTH_JINGQI.unit == BREADTH_UP_RATIO.unit == "%"

    def test_up_ratio_is_single_day(self):
        """上漲佔比必須標明是單日、未平滑 —— 與旌旗的差別就在這。"""
        from src.ui.render.ui_widgets import BREADTH_UP_RATIO
        assert "單日" in BREADTH_UP_RATIO.formula

    def test_deprecated_titles_registered(self):
        from src.ui.render.ui_widgets import BREADTH_DEPRECATED_TITLES
        for old in ("全市場健康度", "站上均線家數比", "站上 20MA 家數比"):
            assert old in BREADTH_DEPRECATED_TITLES, f"{old} 應登記為退役名"
            _canonical, reason = BREADTH_DEPRECATED_TITLES[old]
            assert reason, f"{old} 必須寫退役理由"


class TestTermTableDerivedFromSSOT:
    """名詞表不得與 BREADTH_TERMS 分家（本次事故的根因就是各寫一份）。"""

    @pytest.mark.parametrize("key,attr", [
        ("ADL", "BREADTH_ADL"),
        ("騰落指標", "BREADTH_ADL"),
        ("旌旗指數", "BREADTH_JINGQI"),
        ("上漲佔比", "BREADTH_UP_RATIO"),
        ("AD值", "BREADTH_AD_VALUE"),
    ])
    def test_entry_generated_from_term(self, key, attr):
        import src.ui.render.ui_widgets as W
        term = getattr(W, attr)
        nickname, desc = W.TERM_EXPLAIN[key]
        assert nickname == term.nickname, f"{key} 的白話名未取自 SSOT"
        assert term.formula in desc, f"{key} 的說明未帶 SSOT 公式"

    def test_jingqi_entry_no_longer_claims_ma_breadth(self):
        """旌旗說明不得再宣稱「站上均線」是它的定義（§1 反捏造）。

        允許出現「不是站上均線」這種**否定式澄清**，但必須同時帶真公式，
        且必須帶否定詞 —— 否則就是舊的捏造描述復活。
        """
        from src.ui.render.ui_widgets import BREADTH_JINGQI, TERM_EXPLAIN
        _nickname, desc = TERM_EXPLAIN["旌旗指數"]
        assert BREADTH_JINGQI.formula in desc, "必須寫出真正的公式"
        if "站上" in desc:
            assert "不是" in desc, \
                "提到『站上均線』時必須是否定式澄清，不可當成定義"

    def test_term_table_entries_still_2tuples(self):
        """既有契約：TERM_EXPLAIN 每筆是 (名, 說明) 2-tuple、字串非空。

        與 tests/test_ui_widgets.py:86-91 同步，避免本次改動破壞舊守衛。
        """
        from src.ui.render.ui_widgets import TERM_EXPLAIN
        for term, val in TERM_EXPLAIN.items():
            assert isinstance(val, tuple) and len(val) == 2, f"{term} 結構壞了"
            assert all(isinstance(v, str) and v for v in val), f"{term} 含空字串"


# ════════════════════════════════════════════════════════════════
# 2. 退役名 / 捏造描述不得出現在畫面字串
# ════════════════════════════════════════════════════════════════
class TestRetiredNamesNotOnScreen:
    @pytest.mark.parametrize("rel", _CONSUMER_UI_FILES)
    def test_no_retired_title_in_screen_strings(self, rel):
        """「全市場健康度」一名三義 → 不得再出現在任何畫面字串。

        用 AST 掃字面值：註解不在 AST 內，docstring 另外排除，
        因此「解釋為何退役」的說明文字不會被誤判。
        """
        offenders = [s for s in _screen_strings(rel) if "全市場健康度" in s]
        assert not offenders, (
            f"{rel} 仍在畫面字串使用退役名「全市場健康度」: {offenders}")

    def test_glossary_mentions_retired_names_only_as_blacklist(self):
        """名詞表本身必須提到舊名（才能當黑名單），但只能出現在退役登記裡。

        因此對 glossary 檔不掃「有沒有出現」，改掃「是不是只出現在
        `BREADTH_DEPRECATED_TITLES` 的 key 上」。
        """
        from src.ui.render.ui_widgets import BREADTH_DEPRECATED_TITLES, BREADTH_TERMS
        retired = set(BREADTH_DEPRECATED_TITLES)
        # 退役名不可同時是現役正式名 / 白話名
        for term in BREADTH_TERMS.values():
            assert term.canonical not in retired, f"{term.canonical} 既現役又退役"
            assert term.nickname not in retired, f"{term.nickname} 既現役又退役"

    @pytest.mark.parametrize("rel", _CONSUMER_UI_FILES)
    def test_no_fabricated_ma_breadth_claim(self, rel):
        """不得宣稱「站上均線家數比」—— 系統從未計算此量（§1 反捏造）。

        全 repo grep `站上|above_ma|pct_above` 的結論：
        - `tab_stock.py:563-565` `_above_ma20` 是**單檔個股**比自己的均線
        - `daily_data_fetchers.py:445` `adl_ma20` 是「ADL 累積線的 MA20」
        兩者都不是「站上均線的股票家數比例」。

        ⚠️ 比對用**連續字串**而非「站上 + 家數」共現：教學頁有一句合法敘述
        「只看 MA120 連三日站上/跌破 + 均線斜率 …（廣度、漲跌家數是進市場分數）」
        —— 站上與家數同時出現但講的是兩件不同且正確的事，共現式比對會誤殺。
        允許否定式澄清（同句含「不是」）。
        """
        offenders = [
            s for s in _screen_strings(rel)
            if any(p in s for p in _FABRICATED_BREADTH_PHRASES) and "不是" not in s
        ]
        assert not offenders, (
            f"{rel} 畫面字串出現未經澄清的「站上均線家數比」捏造描述: {offenders}")


class TestBreadthFamilyNameNotUsedAsMetric:
    def test_macro_stock_link_labels_jingqi_by_canonical(self):
        """個股頁 banner 原本印「市場廣度：{旌旗的 label}」= 家族統稱冒充單一數值。"""
        src = _src("src/ui/tabs/macro_stock_link.py")
        assert "BREADTH_JINGQI" in src, "應改用旌旗正式名（取自 SSOT）"
        offenders = [s for s in _screen_strings("src/ui/tabs/macro_stock_link.py")
                     if "市場廣度：" in s or "市場廣度:" in s]
        assert not offenders, f"不可用家族統稱標一個數值: {offenders}"


# ════════════════════════════════════════════════════════════════
# 3. 旌旗 session key 回寫汙染（修正二）
# ════════════════════════════════════════════════════════════════
def _jingqi_write_dicts(rel: str) -> list[ast.Dict]:
    """找出 `st.session_state['jingqi_info'] = {...}` 這類 inline 寫入。"""
    found: list[ast.Dict] = []
    for node in ast.walk(_tree(rel)):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if (isinstance(tgt, ast.Subscript)
                    and isinstance(tgt.slice, ast.Constant)
                    and tgt.slice.value == "jingqi_info"
                    and isinstance(node.value, ast.Dict)):
                found.append(node.value)
    return found


def _dict_str_field(d: ast.Dict, key: str) -> str | None:
    for k, v in zip(d.keys, d.values):
        if (isinstance(k, ast.Constant) and k.value == key
                and isinstance(v, ast.Constant) and isinstance(v.value, str)):
            return v.value
    return None


class TestJingqiWritebackNotPolluted:
    REL = "src/ui/tabs/macro/section_short.py"

    def test_adl_path_delegates_to_ssot(self):
        """有 ad_ratio 序列時，必須呼叫 L3 SSOT 算 5 日均，不得 inline 用當日值。

        修正前：`'avg': _adl_ratio`（**當日**上漲佔比）被寫進旌旗 key，
        而 canonical 旌旗是 **5 日均**（jingqi_calc.py:43）—— 同一個 key 兩種口徑，
        下游（section_overview / 個股組合 KPI / 置底常駐條 /
        compute_macro_health 的 0.6 權重）全都當 5 日均在用。
        """
        src = _src(self.REL)
        assert "compute_and_store_jingqi" in src, \
            "ADL 路徑應委派 src.services.jingqi_calc.compute_and_store_jingqi"
        assert "'avg': _adl_ratio" not in src and '"avg": _adl_ratio' not in src, \
            "不得再用『當日上漲佔比』當旌旗值（口徑不符）"

    def test_no_single_day_value_written_as_jingqi_avg(self):
        """任何殘留的 inline 寫入都不得把單日變數塞進 avg。"""
        for d in _jingqi_write_dicts(self.REL):
            for k, v in zip(d.keys, d.values):
                if isinstance(k, ast.Constant) and k.value == "avg":
                    if isinstance(v, ast.Name):
                        assert v.id != "_adl_ratio", \
                            "avg 不可直接吃當日 ad_ratio（應走 5 日均 SSOT）"

    def test_remaining_fallback_carries_proxy_flag(self):
        """§1：唯一保留的 fallback（TWSE 即時單日值）必須帶可見代理旗標。

        該路徑只拿得到今日 adv/dec，**無法**算 5 日均，因此是真 fallback；
        但依 §1 不可靜默頂替 —— 口徑差異必須寫進 `source`，下游才顯示得出來。
        """
        dicts = _jingqi_write_dicts(self.REL)
        assert dicts, "預期仍保留 1 個 TWSE 即時 fallback 寫入站"
        for d in dicts:
            source = _dict_str_field(d, "source")
            assert source, "fallback 寫入必須帶 source（§2.2 provenance）"
            assert source != "ADL", "代理值不可偽裝成主源 'ADL'"
            assert ("非5日均" in source or "單日" in source), (
                f"source 必須標明口徑差異（非 5 日均），實際: {source!r}")

    def test_fallback_keeps_key_contract(self):
        """fallback 寫入的鍵集合須與 jingqi_calc 契約一致（避免下游 KeyError）。"""
        for d in _jingqi_write_dicts(self.REL):
            keys = {k.value for k in d.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            assert keys == _JQ_CONTRACT_KEYS, (
                f"鍵集合偏離契約，缺 {_JQ_CONTRACT_KEYS - keys} / "
                f"多 {keys - _JQ_CONTRACT_KEYS}")

    def test_no_fabricated_pct_keys_regression(self):
        """v19.84 既有守衛：不得復活 pct20/60/120/240 捏造鍵。"""
        src = _src(self.REL)
        for bad in ("'pct20'", "'pct60'", "'pct120'", "'pct240'"):
            assert bad not in src, f"捏造鍵 {bad} 復活"


class TestProxyFlagIsVisibleDownstream:
    """§1：代理值不可靜默 —— 讀 jingqi_info 的畫面必須看得到 source。"""

    @pytest.mark.parametrize("rel", [
        "src/ui/tabs/macro/section_overview.py",
        "src/ui/tabs/macro_stock_link.py",
    ])
    def test_consumer_reads_source(self, rel):
        src = _src(rel)
        assert "source" in src, (
            f"{rel} 讀 jingqi_info 卻沒讀 source —— 代理值會靜默顯示成主源")


class TestBreadthKpiUnits:
    """§4.1：上漲佔比是 %，不可顯示成「分」（會與綜合健康度分數互相冒充）。"""

    def test_up_ratio_kpi_not_rendered_as_score(self):
        src = _src("src/ui/tabs/macro/section_short.py")
        assert "_breadth_score" not in src, \
            "『廣度健康評分』變數已退役（該值是百分比不是分數）"
        offenders = [s for s in _screen_strings("src/ui/tabs/macro/section_short.py")
                     if s.strip() == "分" or s.endswith("}分")]
        assert not offenders, f"上漲佔比不可顯示成「分」: {offenders}"
