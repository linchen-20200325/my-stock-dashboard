# -*- coding: utf-8 -*-
"""G1(2026-08-07)— 餵給 LLM 的月頻總經數字必須帶時效標記。

病史（本檔存在的理由）
────────────────────────────────────────────────────────────────
`shared/staleness.stale_tag`（月度指標過期 → 行首 `[STALE:Nd]`，防 AI 把過期資料
當當期講）**做好了卻從來沒接上**：全 repo 唯一的消費者是
`app_ai_service.build_llm_context`，而它有 **0 個 production caller**。
真正在跑的兩處總經 prompt——

    src/ui/tabs/macro/section_news_ai.py   `_ctx`         （總經 Tab AI 總裁決）
    src/ui/tabs/tab_stock.py               `_macro_lines2`（個股 Tab 首席顧問）

——送進 Gemini 的 NDC / 台灣 PMI / 台灣出口 / 美核心 CPI **連資料日期都沒有**。
一份三個月前的 CPI 與昨天的 VIX 在 prompt 裡長得一模一樣，LLM 沒有辦法分辨。

而 `build_llm_context` 自己因為 0 caller、從未被實際執行過，藏著兩個 bug：

  1. **`threshold=40` 對每一個月頻指標都是錯的。**
     這些 `date` 是**資料歸屬月的月初**（'YYYY-MM-01'），不是公布日。月頻資料在被
     下一期取代前，as_of 年齡本來就會長到「62 天 + 發布延遲」：

         指標          發布延遲   當期資料的 as_of 年齡上限
         台灣 PMI       月後 1d    ~63d
         台灣出口       月後 10d   ~72d
         美核心 CPI     月後 13d   ~75d
         NDC 景氣燈號   月後 27d   ~89d

     ⇒ 40 天門檻會讓**當期**的 CPI / 出口 / NDC **每天都被標成過期**。
     一個 100% 觸發的警告等於沒有警告，LLM 只會學會忽略它 —— §1「不得把過期
     當當期」被反向濫用成「把當期當過期」，一樣是在對使用者說謊。

  2. **`stale_tag(None)` 回空字串 = 沒有日期就默認新鮮。**
     這正好是最危險的一格（`tab_stock` 的 CPI 有 `ma_snap` fallback，那個 dict
     根本不帶日期）。§1：不確定 ≠ 新鮮。

本檔釘的東西
────────────────────────────────────────────────────────────────
  A. **行為**：門檻值、`macro_stale_prefix` 三態（當期 / 過期 / 日期不明）、
     `build_llm_context` 實際吐出來的字串。
  B. **格式**：加了標記之後，prompt 仍然是合法的（bullet 結構 / 章節結構不破）。
  C. **wiring（AST）**：兩處 live prompt 真的把 helper 用在**月頻**那幾行上，
     而且**沒有**誤用在日頻（VIX / US10Y / SOX）上。

── 為什麼 C 用 AST 而不是字串掃描 ─────────────────────────────
本 session 已被「守衛掃字面」的假紅燈擋過 9 次，最大教訓是：
**守衛照抄實作字面，所以它永遠不會發現實作有問題。**
故本檔的 wiring 檢查：
  • 完全走 `ast` —— 註解在 AST 裡不存在，天生不可能誤判；
  • docstring 明確排除；
  • 檢查的是「helper 被呼叫時第一個引數是哪個指標 key」這個**語意**，
    不是「原始碼裡有沒有出現某段文字」；
  • 失敗訊息印出 `檔:行` 與該行原文；
  • `TestGuardItself` 用一段刻意在註解 / docstring 裡寫滿假 wiring 的原始碼，
    證明守衛不會被字面騙到。
"""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pytest

from shared.staleness import (
    MACRO_PUBLICATION_LAG_DAYS,
    MONTHLY_PUBLICATION_MARGIN_DAYS,
    MONTHLY_SUPERSEDE_SPAN_DAYS,
    monthly_stale_threshold,
    staleness_days,
)
from src.services.ai_structured_summary import (
    MACRO_STALE_LEGEND,
    MACRO_STALE_UNKNOWN_TAG,
    build_structured_summary_prompt,
    macro_stale_legend,
    macro_stale_prefix,
)

_REPO = Path(__file__).resolve().parent.parent

# 固定基準日（2026-08-07，週五）—— 所有門檻測試用它注入，不吃執行當天的日期。
_TODAY = dt.date(2026, 8, 7)

# 兩處 live prompt 實際會標記的月頻指標
_MONTHLY_KEYS = {"us_core_cpi", "ism_pmi", "tw_export", "ndc_signal"}


# ══════════════════════════════════════════════════════════════
# A-1. 門檻本身（L0 SSOT）
# ══════════════════════════════════════════════════════════════
class TestMonthlyStaleThreshold:

    @pytest.mark.parametrize("key,lag", sorted(MACRO_PUBLICATION_LAG_DAYS.items()))
    def test_threshold_is_span_plus_lag_plus_margin(self, key, lag):
        assert monthly_stale_threshold(key) == (
            MONTHLY_SUPERSEDE_SPAN_DAYS + lag + MONTHLY_PUBLICATION_MARGIN_DAYS)

    def test_every_threshold_exceeds_the_old_hardcoded_40(self):
        """回歸釘：舊的 `threshold=40` 對**每一個**月頻指標都太緊。

        這條就是 G1 修的核心 bug —— 40 天以下的門檻會讓當期資料天天被誤標。
        """
        for key in MACRO_PUBLICATION_LAG_DAYS:
            assert monthly_stale_threshold(key) > 40, (
                f"{key} 的過期門檻 {monthly_stale_threshold(key)}d ≤ 40d —— "
                f"月頻資料的 as_of 是月初，當期資料本來就會超過 40 天")

    def test_unregistered_indicator_raises(self):
        """§1 Fail Loud：未登錄的指標不得靜默套一個預設門檻。"""
        with pytest.raises(KeyError):
            monthly_stale_threshold("vix")          # 日頻，不該走月頻門檻
        with pytest.raises(KeyError):
            monthly_stale_threshold("不存在的指標")

    def test_lag_table_covers_every_wired_key(self):
        """live prompt 標記的每個 key 都必須有登錄的發布延遲，否則 runtime KeyError。"""
        missing = _MONTHLY_KEYS - set(MACRO_PUBLICATION_LAG_DAYS)
        assert not missing, f"這些指標已接進 prompt 卻沒登錄發布延遲：{sorted(missing)}"


# ══════════════════════════════════════════════════════════════
# A-2. `macro_stale_prefix` 三態
# ══════════════════════════════════════════════════════════════
class TestMacroStalePrefix:

    # ── 當期（在正常發布週期內）→ 不得標記 ──────────────────────
    @pytest.mark.parametrize("key,as_of,age", [
        # 2026-08-07 當下，各指標「最新一筆」的真實 as_of 與年齡
        ("us_core_cpi", "2026-06-01", 67),   # 7 月 CPI ~8/13 才公布 → 最新是 6 月
        ("tw_export",   "2026-06-01", 67),   # 7 月出口 ~8/09 前後公布
        ("ndc_signal",  "2026-06-01", 67),   # 7 月 NDC ~8/27 才公布
        ("ism_pmi",     "2026-07-01", 37),   # 7 月 PMI 8/01 已公布
    ])
    def test_current_release_is_not_tagged(self, key, as_of, age):
        assert staleness_days(as_of, today=_TODAY) == age, "測資年齡算錯，先修測資"
        assert macro_stale_prefix(key, as_of, today=_TODAY) == "", (
            f"{key} as_of={as_of}（距今 {age} 天）是當期最新一筆，"
            f"門檻 {monthly_stale_threshold(key)}d，不該被標過期")

    def test_current_cpi_would_have_been_falsely_tagged_by_old_40d(self):
        """反向釘死舊行為：同一筆當期 CPI 用舊的 40 天門檻會被誤標。

        沒有這條，未來有人把門檻改回 40 也不會有人發現。
        """
        from shared.staleness import stale_tag
        _days = staleness_days("2026-06-01", today=_TODAY)
        assert stale_tag(_days, threshold=40) == "[STALE:67d] ", "舊行為認定"
        assert macro_stale_prefix("us_core_cpi", "2026-06-01", today=_TODAY) == ""

    # ── 真的漏掉一期以上 → 必須標記 ────────────────────────────
    @pytest.mark.parametrize("key,as_of", [
        ("us_core_cpi", "2026-04-01"),   # 128d > 82d
        ("tw_export",   "2026-05-01"),   # 98d  > 79d
        ("ism_pmi",     "2026-05-01"),   # 98d  > 70d
        ("ndc_signal",  "2026-03-01"),   # 159d > 96d
    ])
    def test_genuinely_missed_release_is_tagged(self, key, as_of):
        _days = staleness_days(as_of, today=_TODAY)
        out = macro_stale_prefix(key, as_of, today=_TODAY)
        assert out == f"[STALE:{_days}d] ", (
            f"{key} as_of={as_of} 距今 {_days} 天，已超過門檻 "
            f"{monthly_stale_threshold(key)}d，必須標記；實得 {out!r}")

    # ── 沒有日期 → 不得當成新鮮（§1）──────────────────────────
    @pytest.mark.parametrize("bad_date", [None, "", "  ", "not-a-date", float("nan")])
    def test_missing_date_is_never_treated_as_fresh(self, bad_date):
        out = macro_stale_prefix("us_core_cpi", bad_date, today=_TODAY)
        assert out == MACRO_STALE_UNKNOWN_TAG, (
            f"date={bad_date!r} 無法判定，卻回 {out!r} —— "
            f"空字串等於默認它是新鮮的（§1：不確定 ≠ 新鮮）")
        assert "[STALE:" in out, "未知日期也必須是可被圖例解釋的 STALE 家族標記"

    def test_month_only_date_is_parsed(self):
        """海關出口的 date 是 'YYYY-MM'（非 'YYYY-MM-DD'），不得因此判成日期不明。"""
        assert macro_stale_prefix("tw_export", "2026-06", today=_TODAY) == ""
        assert MACRO_STALE_UNKNOWN_TAG not in macro_stale_prefix(
            "tw_export", "2026-06", today=_TODAY)

    def test_unregistered_key_raises(self):
        with pytest.raises(KeyError):
            macro_stale_prefix("vix", "2026-08-06", today=_TODAY)


# ══════════════════════════════════════════════════════════════
# A-3. 圖例
# ══════════════════════════════════════════════════════════════
class TestMacroStaleLegend:

    def test_legend_only_when_something_is_tagged(self):
        assert macro_stale_legend("• 台灣 PMI：52.0") == ""
        assert macro_stale_legend("") == ""
        assert macro_stale_legend(None) == ""
        assert macro_stale_legend("• [STALE:98d] 台灣 PMI：52.0") == MACRO_STALE_LEGEND

    def test_legend_covers_both_tag_shapes(self):
        assert macro_stale_legend(f"• {MACRO_STALE_UNKNOWN_TAG}CPI") == MACRO_STALE_LEGEND

    def test_legend_explains_what_the_tag_means(self):
        """圖例必須真的解釋標記 —— 只丟 `[STALE:Nd]` 給 LLM 等於沒標。"""
        assert "[STALE:Nd]" in MACRO_STALE_LEGEND
        assert MACRO_STALE_UNKNOWN_TAG.strip() in MACRO_STALE_LEGEND
        # 必須明講「不得當成當期」這個行為指令，而不只是描述性文字
        assert "不得" in MACRO_STALE_LEGEND


# ══════════════════════════════════════════════════════════════
# B. `build_llm_context` 實際輸出（行為斷言，不掃原始碼）
# ══════════════════════════════════════════════════════════════
class _StubST:
    """取代 `app_ai_service.st`。

    刻意塞一組 sentinel 進 `session_state`：若 stub 沒被真的讀到，
    `test_stub_session_state_is_actually_read` 會紅 —— 避免「patch 目標失效
    但測試照樣綠」（本 session 已掃出 22 處這種假綠）。
    """

    def __init__(self, session_state=None):
        self.session_state = session_state if session_state is not None else {}
        self.secrets: dict = {}


@pytest.fixture
def ctx(monkeypatch):
    """回一個 `(macro_info, session_state) -> str` 的呼叫器。"""
    from src.services import app_ai_service as A

    def _call(macro_info: dict, session_state: dict | None = None) -> str:
        stub = _StubST(session_state)
        monkeypatch.setattr(A, "st", stub)
        out = A.build_llm_context(macro_info)
        _call.last_stub = stub
        return out

    return _call


def _bullet_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip()]


class TestBuildLlmContextBehaviour:

    def test_stub_session_state_is_actually_read(self, ctx):
        """先證明 patch 有效：session_state 的 M1B 真的進了輸出。"""
        out = ctx({}, {"m1b_m2_info": {"m1b_yoy": 5.0, "m2_yoy": 3.0}})
        assert "M1B=5.0%" in out and "Gap=+2.00%" in out, (
            "stub 的 session_state 沒被讀到 —— patch 目標失效，"
            "本檔其餘 session_state 相關斷言全部不可信")

    def test_stale_monthly_indicator_is_tagged_and_explained(self, ctx):
        _old = (dt.date.today() - dt.timedelta(days=200)).isoformat()
        out = ctx({"us_core_cpi": {"yoy": 3.1, "date": _old}})
        assert "美國核心 CPI YoY" in out
        assert "[STALE:" in out, "距今 200 天的 CPI 必須標過期"
        assert MACRO_STALE_LEGEND in out, "標了卻不解釋，LLM 讀不懂這個標記"
        assert _old in out, "過期時更要把資料日期講出來"

    def test_current_monthly_indicator_has_no_tag_and_no_legend(self, ctx):
        """距今 30 天的 PMI 是當期（門檻 70d）→ 不標、也不該出現圖例。"""
        _recent = (dt.date.today() - dt.timedelta(days=30)).isoformat()
        out = ctx({"ism_pmi": {"value": 52.3, "date": _recent}})
        assert "台灣 PMI" in out and "52.3" in out
        assert "[STALE:" not in out, "當期資料被誤標過期"
        assert MACRO_STALE_LEGEND not in out, "沒有過期就不該塞圖例（製造雜訊）"

    def test_daily_indicator_is_never_tagged(self, ctx):
        """VIX 是日頻：不套月頻標記，也不會因為 macro_info 沒帶 date 就被標。"""
        out = ctx({"vix": {"current": 18.4, "ma20": 17.1}})
        assert "VIX 恐慌指數：18.4" in out
        assert "[STALE:" not in out
        assert MACRO_STALE_LEGEND not in out

    def test_missing_date_is_tagged_not_silently_fresh(self, ctx):
        """§1：月頻指標有值但沒有日期 → 必須標「日期不明」，不得靜默放行。"""
        out = ctx({"tw_export": {"yoy": 12.3}})           # 沒有 'date'
        assert "台灣出口 YoY" in out and "+12.3%" in out
        assert MACRO_STALE_UNKNOWN_TAG in out
        assert "資料月份不明" in out, "行內也要照實寫，不留白讓 LLM 以為是本月"
        assert MACRO_STALE_LEGEND in out

    def test_ndc_line_carries_its_as_of(self, ctx):
        """NDC 那行原本漏了資料月份（其餘三行都有）。"""
        out = ctx({"ndc_signal": {"score": 27, "date": "2026-06-01"}})
        assert "NDC 景氣燈號分數：27/45" in out
        assert "2026-06-01" in out

    def test_empty_macro_info_says_loading(self, ctx):
        out = ctx({})
        assert "量化數據載入中" in out
        assert "[STALE:" not in out

    # ── 格式：加了標記之後仍是合法輸出 ──────────────────────────
    def test_output_is_still_well_formed_bullets_when_tagged(self, ctx):
        _old = (dt.date.today() - dt.timedelta(days=300)).isoformat()
        out = ctx(
            {
                "vix": {"current": 18.4, "ma20": 17.1},
                "us_core_cpi": {"yoy": 3.1, "date": _old},
                "ism_pmi": {"value": 48.0, "date": _old},
                "tw_export": {"yoy": -2.0, "date": _old},
                "ndc_signal": {"score": 21, "date": _old},
            },
            {"m1b_m2_info": {"m1b_yoy": 5.0, "m2_yoy": 3.0},
             "bias_info": {"bias_240": 8.5}},
        )
        lines = _bullet_lines(out)
        assert lines[0] == MACRO_STALE_LEGEND, "圖例應在最前面一行"
        data_lines = lines[1:]
        assert len(data_lines) == 7, f"應有 7 條數據行，實得 {len(data_lines)}：{data_lines}"
        assert all(ln.startswith("• ") for ln in data_lines), (
            f"標記破壞了 bullet 格式：{[ln for ln in data_lines if not ln.startswith('• ')]}")
        # 標記必須在 bullet 之後、指標名之前（`• [STALE:...] 指標…`）
        tagged = [ln for ln in data_lines if "[STALE:" in ln]
        assert len(tagged) == 4, f"4 條月頻全過期，實得 {len(tagged)}"
        assert all(ln.startswith("• [STALE:") for ln in tagged)
        # 日頻 3 條（VIX / M1B / BIAS240）不得被標
        assert len([ln for ln in data_lines if "[STALE:" not in ln]) == 3

    def test_tagged_context_survives_structured_prompt(self, ctx):
        """標記後的段落塞進共用 prompt 元件，章節結構不得被破壞。"""
        _old = (dt.date.today() - dt.timedelta(days=300)).isoformat()
        macro_block = ctx({"us_core_cpi": {"yoy": 3.1, "date": _old}})
        prompt = build_structured_summary_prompt(
            "台股大盤現在的狀況",
            [{"name": "景氣、資金、利率這些關鍵數字現在長怎樣", "data": macro_block},
             {"name": "熱錢動向", "data": "（無熱錢資料）"}],
            news_text="- [Reuters] 測試新聞",
        )
        assert "[STALE:" in prompt, "標記必須原封進到最終 prompt"
        assert MACRO_STALE_LEGEND in prompt
        # 結構完整性
        assert "## 🧾 台股大盤現在的狀況｜白話總整理" in prompt
        assert "【第1節：景氣、資金、利率這些關鍵數字現在長怎樣】" in prompt
        assert "【第2節：熱錢動向】" in prompt
        assert "以下 2 個章節**全部都要輸出**" in prompt
        assert "### ✅ 一句話總結" in prompt


# ══════════════════════════════════════════════════════════════
# C. live prompt 的 wiring（AST，不掃字面）
# ══════════════════════════════════════════════════════════════
# 註：本組守衛**不需要**顯式排除 docstring / 註解。
# 它比對的是 `ast.Call` 節點（「這裡真的呼叫了 helper，第一個引數是哪個指標」），
# 而 docstring 是 `ast.Constant`、註解在 AST 裡根本不存在 —— 兩者都不可能被誤判成
# 呼叫。`TestGuardItself` 用一段刻意在註解 / docstring / 字串字面裡寫滿假 wiring 的
# 原始碼證明這一點。


def _append_calls(tree: ast.AST, list_name: str) -> list[ast.Call]:
    """`<list_name>.append(...)` 的所有呼叫節點。"""
    return [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and n.func.attr == "append"
        and isinstance(n.func.value, ast.Name) and n.func.value.id == list_name
    ]


def _helper_keys_in(node: ast.AST, helper: str) -> list[tuple[str, int]]:
    """子樹內 `helper('<key>', ...)` 的 (key, lineno)。非字面 key 一律忽略。"""
    out: list[tuple[str, int]] = []
    for n in ast.walk(node):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == helper and n.args
                and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str)):
            out.append((n.args[0].value, n.lineno))
    return out


def _calls_helper(tree: ast.AST, helper: str) -> bool:
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == helper for n in ast.walk(tree))


def _load(rel: str) -> tuple[ast.AST, list[str]]:
    src = (_REPO / rel).read_text(encoding="utf-8")
    return ast.parse(src), src.splitlines()


_SITES = [
    # (檔案, 累積 prompt 行的 list 變數, 標記 helper, 圖例 helper)
    ("src/ui/tabs/macro/section_news_ai.py", "_ctx", "_stale", "_macro_stale_legend"),
    ("src/ui/tabs/tab_stock.py", "_macro_lines2", "_msp2", "_msl2"),
]


class TestLivePromptWiring:
    """兩處**真的在跑**的總經 prompt 必須把標記用在月頻、且只用在月頻。"""

    @pytest.mark.parametrize("rel,list_name,helper,legend", _SITES)
    def test_anchor_exists(self, rel, list_name, helper, legend):
        """錨點消失 → 守衛靜默失效，先擋在這裡。"""
        tree, _ = _load(rel)
        assert _append_calls(tree, list_name), (
            f"{rel}: 找不到任何 `{list_name}.append(...)` —— 變數被改名？"
            f"請同步更新本檔 _SITES，否則本組守衛等於沒有")

    @pytest.mark.parametrize("rel,list_name,helper,legend", _SITES)
    def test_monthly_indicators_are_tagged(self, rel, list_name, helper, legend):
        tree, lines = _load(rel)
        found: dict[str, int] = {}
        for call in _append_calls(tree, list_name):
            for key, lineno in _helper_keys_in(call, helper):
                found[key] = lineno
        expected = _MONTHLY_KEYS & _keys_present_in_site(rel)
        missing = expected - set(found)
        _done = "\n".join(f"  {k} → {rel}:{v}: {lines[v - 1].strip()}"
                          for k, v in sorted(found.items()))
        assert not missing, (
            f"{rel} 的 `{list_name}` 內，這些月頻指標沒有套時效標記："
            f"{sorted(missing)}\n已套的：\n{_done or '  （一個都沒有）'}")

    @pytest.mark.parametrize("rel,list_name,helper,legend", _SITES)
    def test_daily_indicators_are_not_tagged(self, rel, list_name, helper, legend):
        """日頻指標（VIX / US10Y / SOX）套月頻門檻 = 語意錯，且會 KeyError。"""
        tree, lines = _load(rel)
        bad: list[str] = []
        for call in _append_calls(tree, list_name):
            for key, lineno in _helper_keys_in(call, helper):
                if key not in MACRO_PUBLICATION_LAG_DAYS:
                    bad.append(f"{rel}:{lineno}: {lines[lineno - 1].strip()}")
        assert not bad, (
            "以下行把月頻時效標記套在未登錄（多為日頻）的指標上 —— "
            "`monthly_stale_threshold` 會 KeyError：\n" + "\n".join(bad))

    @pytest.mark.parametrize("rel,list_name,helper,legend", _SITES)
    def test_legend_is_attached(self, rel, list_name, helper, legend):
        """標了卻不附圖例 = LLM 讀不懂 `[STALE:Nd]`，等於沒標。"""
        tree, _ = _load(rel)
        assert _calls_helper(tree, legend), (
            f"{rel}: 沒有呼叫 `{legend}(...)` —— 過期標記缺少圖例")


def _keys_present_in_site(rel: str) -> set[str]:
    """該 site 實際會餵哪些月頻指標（個股 Tab 只餵 CPI / PMI，沒有 NDC / 出口）。"""
    if rel.endswith("tab_stock.py"):
        return {"us_core_cpi", "ism_pmi"}
    return set(_MONTHLY_KEYS)


class TestSectionNewsAiHelpers:
    """`section_news_ai` 的兩個 module-level helper 直接跑一次（行為，非結構）。"""

    def test_stale_and_asof(self):
        from src.ui.tabs.macro import section_news_ai as S

        assert S._asof({"date": "2026-06-01"}) == "資料月份 2026-06-01"
        assert S._asof({}) == "資料月份不明"
        assert S._asof(None) == "資料月份不明"
        # 200 天前 → 任何月頻指標都超過門檻
        _old = (dt.date.today() - dt.timedelta(days=200)).isoformat()
        assert "[STALE:" in S._stale("ism_pmi", {"date": _old})
        assert S._stale("ism_pmi", {}) == MACRO_STALE_UNKNOWN_TAG
        # 30 天前 → 當期
        _new = (dt.date.today() - dt.timedelta(days=30)).isoformat()
        assert S._stale("ism_pmi", {"date": _new}) == ""


# ══════════════════════════════════════════════════════════════
# D. 守衛自檢 —— 證明它不是在掃字面
# ══════════════════════════════════════════════════════════════
_DECOY = '''
"""這個 docstring 裡寫滿假 wiring：
_ctx.append(f'{_stale("us_core_cpi", _d)}CPI')
_macro_lines2.append(f'{_msp2("ism_pmi", d)}PMI')
"""
# 註解也寫一份：_ctx.append(f'{_stale("tw_export", _d)}出口')
def f():
    """_stale("ndc_signal", x)"""
    other = []
    other.append("_stale('ism_pmi', d)")     # 字串字面，不是呼叫
    _ctx.append(f'{_stale("vix", _d)}VIX')   # ← 唯一真的呼叫
'''


class TestGuardItself:

    def test_not_fooled_by_comments_docstrings_or_string_literals(self):
        tree = ast.parse(_DECOY)
        keys: list[str] = []
        for call in _append_calls(tree, "_ctx"):
            keys += [k for k, _ in _helper_keys_in(call, "_stale")]
        assert keys == ["vix"], (
            f"守衛被註解 / docstring / 字串字面騙到了：{keys} —— "
            f"只有真正的呼叫節點才算 wiring")

    def test_string_literal_that_looks_like_a_call_is_not_counted(self):
        """`other.append("_stale('ism_pmi', d)")` 是字串,不是呼叫。"""
        tree = ast.parse(_DECOY)
        keys: list[str] = []
        for call in _append_calls(tree, "other"):
            keys += [k for k, _ in _helper_keys_in(call, "_stale")]
        assert keys == []

    def test_append_calls_scoped_to_the_named_list(self):
        tree = ast.parse(_DECOY)
        assert len(_append_calls(tree, "_ctx")) == 1
        assert len(_append_calls(tree, "other")) == 1
        assert _append_calls(tree, "不存在的變數") == []
