"""tests/test_h2_naming_and_fake_readings.py — H2「名字與內容不符」批次回歸網（2026-08）。

守六件事，**行為斷言優先**；只有在行為測不到「有沒有退回舊寫法」時才補 AST 守衛
（一律排除註解/docstring，失敗訊息印出該行原文）。

  ① `v5_modules.calc_relative_strength`：大盤 σ 不可用時回 `None`，**不再回 0.0**
     （0.0σ 會被 RS 分級判成「⚪ 同步大盤」= 把「算不出來」顯示成「已測量、與大盤同步」）。
  ② 🔭 選股網總覽卡「本次因子」：三個裸 `len()` 改為 tier 過濾後的分子/分母。
  ③ `compute_twii_bias` 的 MA240 命名 → **WONTFIX**，本檔改守「揭露現況不退化」。
  ④ `tab_stock_picker` 的「💎 高息網」殘留（該模組全 repo 零定義）。
  ⑤ `data_registry_panel` expander 恆展開 → 意圖不明，**保留現狀 + 釘住**。
  ⑥ 「30,000 口 ≈ 75 億」數量級 → 口徑未定，改守可驗證的換算事實。

⚠️ 本檔**不得**依賴執行當天日期（registry panel 一律用 'N/A' / 'event' 頻率繞開
   `date.today()`）；有 monkeypatch 之處一律同時斷言 mock 真的被呼叫過。
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[1]


# ══════════════════════════════════════════════════════════════════════════
# 共用：假的 streamlit（讓 L5 render 函式可在無 runtime 下跑並記錄呼叫）
# ══════════════════════════════════════════════════════════════════════════
class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeST:
    """只實作被測 render 路徑用到的 st.* API，並把呼叫記下來。"""

    def __init__(self, session_state: dict | None = None):
        self.session_state = session_state if session_state is not None else {}
        self.markdown_calls: list[str] = []
        self.caption_calls: list[str] = []
        self.info_calls: list[str] = []
        self.expander_calls: list[tuple[str, object]] = []

    def markdown(self, body="", *a, **kw):
        self.markdown_calls.append(str(body))

    def caption(self, body="", *a, **kw):
        self.caption_calls.append(str(body))

    def info(self, body="", *a, **kw):
        self.info_calls.append(str(body))

    def warning(self, body="", *a, **kw):
        self.info_calls.append(str(body))

    def expander(self, label="", *a, **kw):
        self.expander_calls.append((str(label), kw.get("expanded")))
        return _FakeCtx()

    @property
    def all_text(self) -> str:
        return "\n".join(self.markdown_calls + self.caption_calls + self.info_calls
                         + [lbl for lbl, _ in self.expander_calls])


# ══════════════════════════════════════════════════════════════════════════
# AST 工具（守衛用；一律看語法樹，不掃字串 → 註解 / docstring 自動被排除）
# ══════════════════════════════════════════════════════════════════════════
def _parse(rel_path: str) -> tuple[ast.Module, str]:
    # utf-8-sig：有無 BOM 都能解析（BOM 殘留會讓 ast.parse 直接 SyntaxError）
    src = (_ROOT / rel_path).read_text(encoding="utf-8-sig")
    return ast.parse(src), src


def _seg(src: str, node: ast.AST) -> str:
    """節點原文（失敗訊息用；印出真正惹禍的那一行，不是我猜的字串）。"""
    out = ast.get_source_segment(src, node)
    return out if out else f"<line {getattr(node, 'lineno', '?')}>"


def _func_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"AST 找不到函式 {name}（是不是被改名/刪了？）")


# ══════════════════════════════════════════════════════════════════════════
# 合成 K 線（不觸網）
# ══════════════════════════════════════════════════════════════════════════
def _wiggly(n: int = 150, total_ret: float = 0.10, noise: float = 0.012,
            seed: int = 7) -> pd.DataFrame:
    """帶日內波動的等比路徑 → 保證 pct_change().std() > 0。"""
    rng = np.random.RandomState(seed)
    drift = (1 + total_ret) ** (1 / (n - 1)) - 1
    rets = drift + rng.normal(0, noise, n)
    rets[0] = 0.0
    close = 100 * np.cumprod(1 + rets)
    return pd.DataFrame({"close": close},
                        index=pd.date_range("2026-01-01", periods=n, freq="D"))


def _flat(n: int = 150, value: float = 20000.0) -> pd.DataFrame:
    """完全不動的序列 → σ 恰為 0（模擬「大盤序列凍結」的管線事故）。"""
    return pd.DataFrame({"close": [value] * n},
                        index=pd.date_range("2026-01-01", periods=n, freq="D"))


# ══════════════════════════════════════════════════════════════════════════
# ① calc_relative_strength：σ 不可用 → None，不是 0.0
# ══════════════════════════════════════════════════════════════════════════
class TestRelativeStrengthNoFakeZero:

    def test_frozen_market_gives_none_not_synced_with_market(self):
        """大盤序列凍結（σ=0）→ avg_rs=None，且**不得**被判成「同步大盤」。

        這正是舊碼的假讀數：0.0σ 落在 [RS_SIGMA_LAG_MAX, RS_SIGMA_MILD_MIN)
        ⇒ 分級為「⚪ 同步大盤」⇒ 畫面顯示「與大盤連動，無特別籌碼支撐」，
        而真相是「大盤波動率算不出來，RS 的分母不成立」。
        """
        from src.compute.strategy.v5_modules import calc_relative_strength

        out = calc_relative_strength(_wiggly(), _flat(), periods=(20, 60, 120))

        assert out["avg_rs"] is None, "σ 不可用時 avg_rs 必須是 None（不確定 ≠ 中性）"
        assert all(v is None for v in out["rs_scores"].values()), \
            f"逐週期 rs 也必須是 None，實得 {out['rs_scores']}"
        assert "同步大盤" not in out["signal"], \
            f"σ 算不出來卻宣稱『同步大盤』= 假讀數，signal={out['signal']!r}"
        assert "無法標準化" in out["signal"], f"signal={out['signal']!r}"
        # 報酬是真讀數 → 不該連它一起丟（σ 不可用 ≠ 報酬不可用）
        assert out["avg_stock_ret"] is not None and out["avg_market_ret"] is not None
        assert out["avg_market_ret"] == pytest.approx(0.0, abs=1e-9), \
            "凍結序列的區間報酬應為 0%"

    def test_rs_leader_screener_marks_insufficient_when_market_sigma_dead(self):
        """端到端：大盤 σ 死掉時，抗跌 RS 排行必須是**空的**，不是全池 0.0σ。

        舊行為：每一檔都拿到 rs=0.0 → tier「同步大盤」→ 全池進榜（RS_RANKABLE_TIERS
        含 TIER_SYNC）→ 使用者看到一張「每檔都 0.00σ」的排行表卻不知道是壞的。
        """
        from shared.rs_screen_thresholds import (
            RS_MIN_ALIGNED_ROWS, TIER_INSUFFICIENT,
        )
        from src.compute.screener import rs_leader_screener as rl

        assert RS_MIN_ALIGNED_ROWS <= 150, (
            "前提失效：合成序列 150 天不足以通過對齊門檻，本測試會**假通過**"
            "（所有結果都會是資料不足，與 σ 無關）。請調長合成序列。")

        stocks = [{"stock_id": f"000{i}", "name": "", "df": _wiggly(seed=i)}
                  for i in range(3)]

        # 正對照：大盤健康時，同一批股票**確實**排得出來 → 證明上面不是假通過
        healthy = rl.rank_rs_leaders(stocks, _wiggly(seed=99, total_ret=-0.2),
                                     lookback=60)
        assert len(healthy) == 3, f"正對照失敗，排行={healthy}"

        # 反對照：大盤 σ 死掉 → 全判資料不足，排行為空
        scored = [rl.score_rs_leader(s, _flat(), lookback=60) for s in stocks]
        assert [s.tier for s in scored] == [TIER_INSUFFICIENT] * 3
        assert rl.rank_rs_leaders(stocks, _flat(), lookback=60) == []

    def test_nan_sigma_also_none(self):
        """σ 為 NaN（全空欄）也走「算不出來」，不落回 0.0。"""
        from src.compute.strategy.v5_modules import calc_relative_strength

        n = 40
        idx = pd.date_range("2026-01-01", periods=n, freq="D")
        # close 全 NaN 只有最後兩點有值 → pct_change().tail(n).std() 仍可能 NaN
        market = pd.DataFrame({"close": [np.nan] * n}, index=idx)
        market.iloc[-1, 0] = 100.0
        out = calc_relative_strength(_wiggly(n=n), market, periods=(20,))
        assert out["avg_rs"] is None, f"NaN σ 必須回 None，實得 {out['avg_rs']}"

    def test_healthy_path_is_bit_for_bit_unchanged(self):
        """σ 正常時，新舊公式必須逐位相同（本次改動對正常路徑零位移）。"""
        from src.compute.strategy.v5_modules import calc_relative_strength

        ds, dm = _wiggly(seed=3), _wiggly(seed=11, total_ret=-0.05)
        periods = (20, 60, 120)
        out = calc_relative_strength(ds, dm, periods=periods)

        # 舊公式逐字重算（σ 都 > 0.01% → 舊碼的 `else 0.0` 分支永不觸發）
        legacy = []
        for n in periods:
            s_ret = (ds["close"].iloc[-1] / ds["close"].iloc[-n] - 1) * 100
            m_ret = (dm["close"].iloc[-1] / dm["close"].iloc[-n] - 1) * 100
            m_std = dm["close"].pct_change().tail(n).std() * 100
            assert m_std > 0.01, "前提失效：合成大盤 σ 應遠大於 0.01%"
            legacy.append(round((s_ret - m_ret) / m_std, 2))
        assert out["avg_rs"] == round(sum(legacy) / len(legacy), 2)
        assert list(out["rs_scores"].values()) == legacy

    def test_sigma_floor_constant_value_unchanged(self):
        """門檻數值本身**未變**（0.01%）—— 變的只有「算不出來時回什麼」。"""
        from shared.signal_thresholds import RS_MARKET_SIGMA_MIN_PCT
        assert RS_MARKET_SIGMA_MIN_PCT == 0.01

    def test_ast_guard_no_zero_fallback_left(self):
        """AST 守衛：`calc_relative_strength` 內不得再有「三元運算 else 0.0」。

        刻意用 AST 而非字串掃描 —— 本次修改留下的**註解**裡就寫了 `else 0.0`
        （在說明為什麼不能這樣寫）；字串掃描會被自己的註解誤判成紅燈。
        """
        tree, src = _parse("src/compute/strategy/v5_modules.py")
        fn = _func_node(tree, "calc_relative_strength")
        bad = [n for n in ast.walk(fn)
               if isinstance(n, ast.IfExp)
               and isinstance(n.orelse, ast.Constant)
               and n.orelse.value == 0.0
               and not isinstance(n.orelse.value, bool)]
        assert not bad, (
            "calc_relative_strength 又出現「算不出來就給 0.0」的三元運算 —— "
            "0.0σ 在 RS 分級裡＝「⚪ 同步大盤」，是假讀數（§1）。惹禍的原文：\n  "
            + "\n  ".join(_seg(src, n) for n in bad))


# ══════════════════════════════════════════════════════════════════════════
# ② 選股網總覽卡「本次因子」：命中數 vs 被評分數
# ══════════════════════════════════════════════════════════════════════════
class TestScreenerFactorHitCounts:

    # ── 前提：三個 len() 之所以錯，是因為母體本來就含「非命中」──────────
    def test_premise_shortage_rankable_includes_weak_tier(self):
        from shared.shortage_screen_thresholds import TIER_ICONS, TIER_WEAK
        from src.services.shortage_screener_service import _RANKABLE_TIERS
        assert TIER_WEAK in _RANKABLE_TIERS, (
            "前提失效：`_shortage_rows` 不再含「不明顯」——"
            "若真的改了，請改回本測試而不是刪掉它。")
        assert TIER_ICONS[TIER_WEAK] == "⬜" and TIER_WEAK == "不明顯"

    def test_premise_rs_rankable_includes_sync_and_lag(self):
        from shared.rs_screen_thresholds import (
            RS_RANKABLE_TIERS, TIER_LAG, TIER_SYNC,
        )
        assert TIER_SYNC in RS_RANKABLE_TIERS and TIER_LAG in RS_RANKABLE_TIERS, (
            "前提失效：RS 排行不再含同步/落後分級 → 「抗跌 N」才會成立。")

    def test_premise_rows_carry_tier_column(self):
        """`_tier` 是 to_row() 的固定欄位（分子過濾靠它）。"""
        from shared.rs_screen_thresholds import TIER_ICONS as _RS_ICONS, TIER_LEAD
        from shared.shortage_screen_thresholds import (
            TIER_ICONS as _SH_ICONS, TIER_STRONG,
        )
        from src.compute.screener.rs_leader_screener import RsLeaderScore
        from src.compute.screener.shortage_screener import ShortageScore

        sh = ShortageScore(stock_id="2330", name="", total=80.0, tier=TIER_STRONG,
                           tier_icon=_SH_ICONS[TIER_STRONG], c1_contract_liab=20.0,
                           c2_gross_margin=20.0, c3_inventory_days=20.0,
                           c4_revenue_yoy=20.0, cl_na=False)
        assert sh.to_row()["_tier"] == TIER_STRONG

        rs = RsLeaderScore(stock_id="2330", name="", avg_rs=1.5, tier=TIER_LEAD,
                           tier_icon=_RS_ICONS[TIER_LEAD], stock_ret_pct=10.0,
                           market_ret_pct=1.0, excess_pct=9.0, beat_market=True,
                           lookback=60)
        assert rs.to_row()["_tier"] == TIER_LEAD

    def test_premise_trend_map_keeps_zero_favorable_count(self, monkeypatch):
        """`build_trend_map` 保留 favorable_count==0 的檔 ⇒ len() ≠ 轉強家數。"""
        import src.services.fundamental_screener_service as svc

        calls: list[bool] = []

        def _fake_trends(*, refresh: bool = False):
            calls.append(refresh)
            return pd.DataFrame({
                "stock_id": ["1101", "2330", "3008", "9999"],
                "favorable_count": [0, 1, 4, 0],
                "favorable_of": [4, 4, 4, 0],   # 9999 = 全算不出來 → 應被丟掉
            })

        monkeypatch.setattr(svc, "get_cross_quarter_trends", _fake_trends)
        out = svc.build_trend_map()

        assert calls == [False], "monkeypatch 的 get_cross_quarter_trends 沒有被呼叫到"
        assert set(out) == {"1101", "2330", "3008"}
        assert out["1101"] == 0, "favorable_count==0 仍在 map 內（＝ len() 不是命中數）"
        assert len(out) == 3 and sum(1 for v in out.values() if v > 0) == 2

    # ── 行為：summarize_factor_hits ──────────────────────────────────
    def _sh_rows(self):
        from shared.shortage_screen_thresholds import (
            TIER_MID, TIER_STRONG, TIER_WEAK,
        )
        return [{"代碼": "1", "_tier": TIER_STRONG},
                {"代碼": "2", "_tier": TIER_MID},
                {"代碼": "3", "_tier": TIER_WEAK},
                {"代碼": "4", "_tier": TIER_WEAK}]

    def _rs_rows(self):
        from shared.rs_screen_thresholds import (
            TIER_LAG, TIER_LEAD, TIER_MILD, TIER_SYNC,
        )
        return [{"代碼": "1", "_tier": TIER_LEAD},
                {"代碼": "2", "_tier": TIER_MILD},
                {"代碼": "3", "_tier": TIER_SYNC},
                {"代碼": "4", "_tier": TIER_LAG},
                {"代碼": "5", "_tier": TIER_LAG}]

    def test_hits_are_tier_filtered_not_raw_len(self):
        from src.ui.tabs.tab_stock_picker import summarize_factor_hits

        bits = summarize_factor_hits(
            ["shortage", "rs_leader", "trend"],
            shortage_rows=self._sh_rows(),
            rs_rows=self._rs_rows(),
            trend_map={"a": 0, "b": 1, "c": 4, "d": 0})
        joined = " · ".join(bits)

        assert len(bits) == 3, joined
        # 缺貨：4 檔被評分、其中 2 檔真有訊號（強+中度）
        assert "缺貨 訊號2/已評分4" in joined, joined
        # RS：5 檔進排行、其中 2 檔偏強以上（逆勢強+偏強抗跌）
        assert "RS 偏強以上2/已排名5" in joined, joined
        # 跨季：4 檔算得出來、其中 2 檔至少一項方向為佳
        assert "跨季 佳項>0 共2/可算4" in joined, joined
        # 舊文案的三個謊不得復活
        assert "缺貨命中" not in joined and "抗跌RS 5" not in joined, joined

    def test_unscanned_factor_produces_no_phrase(self):
        """None ＝ 沒掃 / 掃失敗 → 不產生片語（§1 掃失敗不假報 0）。"""
        from src.ui.tabs.tab_stock_picker import summarize_factor_hits
        assert summarize_factor_hits(["shortage", "rs_leader", "trend"]) == []
        assert summarize_factor_hits(["shortage"], rs_rows=self._rs_rows()) == []

    def test_scanned_but_empty_shows_zero_over_zero(self):
        """`[]` ＝ 掃了但零結果 → 誠實印 0/0（與「沒掃」語意不同）。"""
        from src.ui.tabs.tab_stock_picker import summarize_factor_hits
        bits = summarize_factor_hits(["shortage"], shortage_rows=[])
        assert bits == ["缺貨 訊號0/已評分0"], bits

    def test_missing_tier_column_does_not_report_fake_zero(self):
        """上游若哪天拿掉 `_tier`，必須說「數不出來」，不得靜默印 0。"""
        from src.ui.tabs.tab_stock_picker import summarize_factor_hits
        bits = summarize_factor_hits(
            ["shortage", "rs_leader"],
            shortage_rows=[{"代碼": "1"}, {"代碼": "2"}],
            rs_rows=[{"代碼": "1"}])
        joined = " · ".join(bits)
        assert "訊號0" not in joined and "偏強以上0" not in joined, joined
        assert "分級欄缺失" in joined, joined
        assert "已評分2" in joined and "已排名1" in joined, joined

    def test_unselected_factor_is_ignored(self):
        from src.ui.tabs.tab_stock_picker import summarize_factor_hits
        bits = summarize_factor_hits(["pe_low"], shortage_rows=self._sh_rows(),
                                     rs_rows=self._rs_rows(), trend_map={"a": 1})
        assert bits == [], bits

    def test_ast_guard_app_uses_helper_not_bare_len(self):
        """AST 守衛：app.py 的 `_hit_bits` 必須由 `summarize_factor_hits` 產生。"""
        tree, src = _parse("app.py")
        assigns = [n for n in ast.walk(tree)
                   if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "_hit_bits"
                           for t in n.targets)]
        assert assigns, "app.py 找不到 `_hit_bits` 賦值（選股網總覽卡被改掉了？）"
        for node in assigns:
            fn = node.value.func if isinstance(node.value, ast.Call) else None
            fname = getattr(fn, "id", None) or getattr(fn, "attr", None)
            assert fname == "summarize_factor_hits", (
                "選股網總覽卡的因子摘要又自己算了 —— 請走 "
                "`tab_stock_picker.summarize_factor_hits`（tier 過濾 + 分子/分母）。"
                f"惹禍的原文：\n  {_seg(src, node)}")


# ══════════════════════════════════════════════════════════════════════════
# ③ compute_twii_bias 的 MA240 命名 → WONTFIX；守「揭露不退化」
# ══════════════════════════════════════════════════════════════════════════
class TestTwiiBiasEstimatedDisclosure:

    def test_ma240_is_really_ma90_but_flag_says_so(self, monkeypatch):
        """資料 90 天時：`ma240` 其實是 MA90，但 `is_estimated=True` 有把它講出來。

        WONTFIX 的理由（見本檔頭 ③）成立的**前提**就是「已揭露」——
        本測試同時釘住「命名確實不精確」與「旗標確實有標」兩件事：
        旗標一旦消失，WONTFIX 立刻不成立，這裡就會紅。
        （monkeypatch 掉 2y fallback → 不觸網、結果確定。）
        """
        import src.data.macro.macro_snapshot as snap

        calls: list[int] = []

        def _no_2y():
            calls.append(1)
            return None          # 模擬離線 / 上游不可用 → 只能用手上的 90 天

        monkeypatch.setattr(snap, "fetch_twii_2y_for_ma240", _no_2y)

        n = 90
        close = np.linspace(20000.0, 21000.0, n)
        df = pd.DataFrame({"Close": close},
                          index=pd.date_range("2026-01-01", periods=n, freq="D"))
        out = snap.compute_twii_bias(df)

        assert calls == [1], "monkeypatch 的 fetch_twii_2y_for_ma240 沒有被呼叫到"
        assert out is not None
        assert out["data_days"] == n
        assert out["is_estimated"] is True, \
            "資料不足 240 天卻沒標 is_estimated —— MA240 這個名稱就真的在說謊了"
        assert out["ma240"] == pytest.approx(float(close.mean())), \
            "`ma240` 在資料不足時就是「全部資料的均值」（此例＝MA90）"

    def test_ma240_is_documented_as_shortened_window(self):
        """文件守衛：`compute_twii_bias` 的 docstring 必須留有「估算」揭露。

        （這條是唯一能守住「別把揭露無聲拿掉」的方式 —— 揭露本身是文字。）
        """
        from src.data.macro.macro_snapshot import compute_twii_bias
        doc = inspect.getdoc(compute_twii_bias) or ""
        assert "is_estimated" in doc and "240" in doc, (
            "compute_twii_bias 的 docstring 不再說明「資料不足 240 天會估算」——"
            f"實際 docstring：\n{doc}")


# ══════════════════════════════════════════════════════════════════════════
# ④ 「💎 高息網」殘留
# ══════════════════════════════════════════════════════════════════════════
class TestYieldScreenerGhostRemoved:

    def test_premise_render_yield_screener_really_absent(self):
        """前提：`render_yield_screener` 全 repo 零定義（該模組不存在）。"""
        import src.ui.tabs.yield_screener as _ys
        assert not hasattr(_ys, "render_yield_screener"), (
            "前提失效：`render_yield_screener` 又出現了 —— "
            "若「高息網」模組復活，請改回本測試而不是刪掉它。")

    def test_source_label_default_is_not_a_dead_module_name(self):
        from src.ui.tabs.tab_stock_picker import render_tab_stock_picker
        default = inspect.signature(render_tab_stock_picker).parameters["source_label"].default
        assert isinstance(default, str) and default
        assert "高息網" not in default, (
            f"`source_label` 預設值又是不存在的模組名：{default!r}")

    def test_default_source_label_actually_reaches_the_screen(self, monkeypatch):
        """行為證明：預設值真的會被渲染出來（所以它不能是謊話）。"""
        import src.ui.tabs.tab_stock_picker as picker

        fake = _FakeST()
        monkeypatch.setattr(picker, "st", fake)
        picker.render_tab_stock_picker(candidates=None)   # candidates 空 → 早退

        assert fake.caption_calls or fake.info_calls, "假的 streamlit 完全沒被呼叫到"
        default = inspect.signature(
            picker.render_tab_stock_picker).parameters["source_label"].default
        assert default in fake.all_text, (
            f"預設 source_label {default!r} 沒出現在畫面文字裡 —— "
            "若已改成不渲染，請更新本測試的前提說明。")
        assert "高息網" not in fake.all_text, fake.all_text

    def test_explicit_source_label_still_wins(self, monkeypatch):
        import src.ui.tabs.tab_stock_picker as picker

        fake = _FakeST()
        monkeypatch.setattr(picker, "st", fake)
        picker.render_tab_stock_picker(candidates=None, source_label="個股組合輸入")
        assert fake.caption_calls, "假的 streamlit 完全沒被呼叫到"
        assert "個股組合輸入" in fake.all_text


# ══════════════════════════════════════════════════════════════════════════
# ⑤ data_registry_panel expander：現狀＝全部展開（刻意保留，釘住）
# ══════════════════════════════════════════════════════════════════════════
class TestRegistryPanelExpanderPinned:

    @staticmethod
    def _state() -> dict:
        """刻意全用 `last_updated='N/A'` → 燈號恆 ⬜，**不吃執行當天日期**。"""
        from shared.data_categories import CAT_CHIPS, CAT_INTL, CAT_TW_MACRO
        return {"data_registry": {
            "道瓊工業 DJI":   {"last_updated": "N/A", "rows": 0,
                               "category": CAT_INTL, "frequency": "daily"},
            "三大法人 外資買賣超": {"last_updated": "N/A", "rows": 0,
                                    "category": CAT_CHIPS, "frequency": "daily"},
            "M1B 資金活水年增率": {"last_updated": "N/A", "rows": 0,
                                   "category": CAT_TW_MACRO, "frequency": "monthly"},
        }}

    def test_every_category_expander_is_expanded(self, monkeypatch):
        """現狀（未變）：所有分類 expander 皆 expanded=True。

        原碼寫成 `expanded=(_cat in _entries[0].get('category', _cat))`，讀起來像
        有條件，實際恆真（`compute_registry_groups` 保證 entry['category'] == _cat，
        且 `x in x` 對字串恆真）。H2 換成字面 `True`：**行為零變更**，只是不再誤導。
        ⚠️ 「原意可能是 `==`」不成立 —— 由同一個不變式，`==` 同樣恆真。
        """
        import src.ui.pages.data_registry_panel as panel

        fake = _FakeST(self._state())
        monkeypatch.setattr(panel, "st", fake)
        panel.render_data_registry_panel()

        assert len(fake.expander_calls) >= 3, (
            f"expander 沒被呼叫到預期次數（假 streamlit 沒生效？）：{fake.expander_calls}")
        assert all(exp is True for _, exp in fake.expander_calls), (
            "資料源完整清單的分類 expander 不再全部展開 —— "
            "這是 UX 行為變更，需 user 核准（§-1），不是順手 bugfix。"
            f"實得：{fake.expander_calls}")

    def test_category_invariant_that_makes_old_expr_tautological(self):
        """釘住讓舊算式恆真的不變式：entry['category'] 必然等於它所屬的 group key。"""
        from src.ui.pages.data_registry_panel import compute_registry_groups
        groups = compute_registry_groups(self._state())
        assert groups
        for cat, entries in groups.items():
            for e in entries:
                assert e["category"] == cat
                assert cat in e["category"]     # 舊算式；恆真
                assert cat == e["category"]     # 改成 `==` 也恆真 → 不是修法

    def test_ast_guard_expanded_is_a_literal_decision(self):
        """AST 守衛：`expanded=` 必須是常數（True/False），不得再是恆真算式。"""
        tree, src = _parse("src/ui/pages/data_registry_panel.py")
        fn = _func_node(tree, "render_data_registry_panel")
        calls = [n for n in ast.walk(fn)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "attr", None) == "expander"]
        assert calls, "render_data_registry_panel 內找不到 st.expander 呼叫"
        for call in calls:
            for kw in call.keywords:
                if kw.arg != "expanded":
                    continue
                assert isinstance(kw.value, ast.Constant), (
                    "`expanded=` 又變成算式了。這裡曾經是一個看似有條件、實際恆真的"
                    "運算式（`_cat in _entries[0]['category']`），誤導了讀者。"
                    "若真要條件展開，請附上判斷依據並更新本測試。"
                    f"惹禍的原文：\n  {_seg(src, kw.value)}")


# ══════════════════════════════════════════════════════════════════════════
# ⑥ 「30,000 口 ≈ 75 億」：口徑未定 → 守可驗證的換算事實
# ══════════════════════════════════════════════════════════════════════════
class TestForeignFuturesDefenseThresholdMagnitude:

    #: TAIFEX 臺股期貨（TX）契約乘數，元/點。此值屬契約規格，不是可調門檻。
    TX_POINT_VALUE_TWD = 200

    def test_threshold_value_unchanged(self):
        """H2 只改文件，**門檻數值一律不動**（動它＝改變 regime 判定）。"""
        from shared.signal_thresholds import FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD
        assert FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD == 30000

    def test_unit_is_tx_equivalent_lots(self):
        """『外資大小』＝ TX 淨口 + 0.25 × MTX 淨口 ⇒ 單位是 TX 當量口。"""
        from src.data.macro.leading_indicators import _MTX_TO_TX_FACTOR
        assert _MTX_TO_TX_FACTOR == 0.25, (
            "小台→大台當量因子變了（MTX 50 元/點 ÷ TX 200 元/點 = 0.25）—— "
            "門檻的單位語意跟著變，docstring 需重寫。")

    @pytest.mark.parametrize("index_points", [15_000, 20_000, 24_000, 30_000])
    def test_notional_is_thousands_of_yi_not_seventy_five(self, index_points):
        """名目口徑下，30,000 口在任何合理指數位階都是**數百～數千億**，不是 75 億。

        這條測的是「舊 docstring 的數量級不可能對」，不是替它挑一個新數字 ——
        名目值隨指數浮動，本來就不該寫死在 docstring 裡（§1 口徑未定則不填）。
        """
        from shared.signal_thresholds import FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD
        notional_yi = (FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD
                       * index_points * self.TX_POINT_VALUE_TWD) / 1e8
        assert notional_yi > 500, f"index={index_points} → {notional_yi:.0f} 億"
        assert notional_yi / 75 > 10, (
            f"名目 {notional_yi:.0f} 億 vs 舊文案「約 75 億」相差 "
            f"{notional_yi / 75:.0f} 倍 —— 兩者不可能是同一個口徑。")

    def test_old_six_yi_claim_is_a_per_point_value(self):
        """更早的「~6 億」對得上的只有『每點價值』（600 萬元/點），不是總值。"""
        from shared.signal_thresholds import FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD
        per_point_twd = FOREIGN_FUTURES_DEFENSE_LOT_THRESHOLD * self.TX_POINT_VALUE_TWD
        assert per_point_twd == 6_000_000          # 600 萬「元/點」
        assert per_point_twd / 1e8 == pytest.approx(0.06)   # ＝ 0.06 億，不是 6 億
