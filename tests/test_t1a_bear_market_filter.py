"""T1-a(2026-08)— 選股網空頭濾網：`regime` 真的改變選股結果。

受測：`src/services/fundamental_screener_service._apply_bear_market_filter`

背景：為什麼需要這個濾網
────────────────────────
流程圖層次 1 標註「總經 → **影響全系統風控係數**」，但實測
`fundamental_screener_service` 全檔 grep `regime` = **0 命中** ——
總經顯示「空頭防禦」時，選股網照樣用同一組門檻選出同一批股票。
那支箭頭在選股引擎上是斷的。

⚠️ 為什麼**不是**改 `beat_only`（重要，勿回退）
──────────────────────────────────────────────
規劃階段曾提案「`beat_only = regime in {bear, caution}`」，實作時查證後**推翻**：

  `fundamental_screener_service.py:487` 的 `run_rs_leader_scan(beat_only=False)`
  決定的是**百分位的分母**，不是濾網開關。改成 True 會讓落後股從 `rs_map`
  (`:343`) 消失 → 對它們而言 RS 因子變成「缺料」→ 依 `:319` 的規則
  **不計入**綜合分平均 → 若 RS 本來在拖累它們，綜合分**反而上升**。

  ⇒ 那個改法會讓「空頭濾網」變成「幫落後股加分」，與意圖完全相反。

故改為在**排名結果**上做顯式後濾，百分位計算完全不動。
本檔 `TestDoesNotTouchPercentileSemantics` 釘住這個決定。

§1 三態必須都講清楚
──────────────────
濾網有三種狀態，其中「想套用但沒 RS 資料」最危險 —— 靜默跳過會讓使用者
以為「總經空頭 → 系統已經幫我濾掉弱勢股」，而實際上什麼都沒發生。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from shared.position_throttle import THROTTLE_VETO_REGIMES
from src.services.fundamental_screener_service import _apply_bear_market_filter

REPO_ROOT = Path(__file__).resolve().parents[1]


def _df(*codes: str) -> pd.DataFrame:
    return pd.DataFrame({"代碼": list(codes), "名稱": [f"N{c}" for c in codes]})


def _rs(*pairs: tuple[str, bool]) -> list[dict]:
    """(代碼, 是否贏過大盤) → rs_rows 形狀（鍵名對齊 rs_leader_service）。"""
    return [{"代碼": c, "贏過大盤": beat, "RS(σ)": 1.0} for c, beat in pairs]


# ════════════════════════════════════════════════════════════════════
# 1. 非防禦態 → 完全不動
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("regime", ["bull", "neutral", "unknown", None, "", "BEAR"])
def test_non_defensive_regime_is_passthrough(regime):
    """只有 canonical 小寫 bear / caution 才套用。

    `'BEAR'`（大寫）刻意也不套用 —— canonical regime 由
    `macro_state_locker.normalize_regime` 統一產出小寫，出現大寫代表
    上游沒正規化，此時**寧可不套用**也不要猜（§1）。
    """
    _in = _df("1101", "2330")
    _out, _note = _apply_bear_market_filter(
        _in, "原註記", regime=regime, rs_rows=_rs(("2330", True)))
    assert len(_out) == 2, "非防禦態不該過濾任何檔"
    assert _note == "原註記", "非防禦態不該追加任何說明（避免每次刷雜訊）"


# ════════════════════════════════════════════════════════════════════
# 2. 防禦態 + 有 RS 資料 → 真的濾掉
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("regime", sorted(THROTTLE_VETO_REGIMES))
class TestFilterApplies:

    def test_keeps_only_market_beaters(self, regime):
        _in = _df("1101", "2330", "2454", "3008")
        _rows = _rs(("2330", True), ("2454", True), ("1101", False), ("3008", False))
        _out, _note = _apply_bear_market_filter(_in, "", regime=regime, rs_rows=_rows)

        assert set(_out["代碼"]) == {"2330", "2454"}
        assert "空頭濾網" in _note
        assert "剔除 2 檔" in _note, f"note 未如實說明剔除數量：{_note}"

    def test_missing_from_rs_rows_is_dropped(self, regime):
        """完全沒出現在 RS 排行裡的檔也要剔除。

        §1：「沒被量測到」不等於「贏過大盤」。空頭中不該因為缺資料就放行。
        """
        _in = _df("2330", "9999")
        _out, _ = _apply_bear_market_filter(
            _in, "", regime=regime, rs_rows=_rs(("2330", True)))
        assert set(_out["代碼"]) == {"2330"}

    def test_code_matching_tolerates_whitespace(self, regime):
        """代碼兩側空白不該造成誤剔（兩邊來源不同，格式未必一致）。"""
        _in = _df(" 2330", "2454 ")
        _rows = [{"代碼": "2330 ", "贏過大盤": True},
                 {"代碼": " 2454", "贏過大盤": True}]
        _out, _ = _apply_bear_market_filter(_in, "", regime=regime, rs_rows=_rows)
        assert len(_out) == 2, "空白造成比對失敗 → 贏過大盤的檔被誤剔"

    def test_all_filtered_out_explains_why(self, regime):
        """全數被剔 → 必須說明那是空頭訊號，不是系統故障。"""
        _in = _df("1101", "3008")
        _out, _note = _apply_bear_market_filter(
            _in, "", regime=regime, rs_rows=_rs(("1101", False), ("3008", False)))
        assert _out.empty
        assert "沒有任何一檔" in _note and "不是系統故障" in _note, (
            f"空表沒有解釋原因 → 使用者會以為系統壞了：{_note}"
        )


# ════════════════════════════════════════════════════════════════════
# 3. §1：想套用但沒 RS 資料 —— 最危險的那一格
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("regime", sorted(THROTTLE_VETO_REGIMES))
@pytest.mark.parametrize("rs_rows", [None, []])
def test_cannot_apply_must_say_so(regime, rs_rows):
    """沒有 RS 資料時**不可靜默跳過**。

    靜默的後果：使用者看到總經「空頭防禦」，以為選股網已經幫他濾掉弱勢股，
    但實際上完全沒有。這正是 §1 禁止的「讓畫面看起來成功」。
    """
    _in = _df("1101", "2330")
    _out, _note = _apply_bear_market_filter(_in, "原註記", regime=regime, rs_rows=rs_rows)

    assert len(_out) == 2, "沒有 RS 資料時不該憑空剔除任何檔"
    assert "未套用" in _note, f"未套用濾網卻沒說 → 使用者會誤以為已生效：{_note}"
    assert "原註記" in _note, "追加說明時吃掉了原本的 note"
    assert "RS" in _note, "沒告訴使用者缺什麼資料、怎麼啟用"


# ════════════════════════════════════════════════════════════════════
# 4. 邊界
# ════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("regime", sorted(THROTTLE_VETO_REGIMES))
class TestEdgeCases:

    def test_empty_df(self, regime):
        _out, _ = _apply_bear_market_filter(
            pd.DataFrame(), "", regime=regime, rs_rows=_rs(("2330", True)))
        assert _out.empty

    def test_none_df(self, regime):
        _out, _note = _apply_bear_market_filter(
            None, "n", regime=regime, rs_rows=_rs(("2330", True)))
        assert _out is None and _note == "n"

    def test_df_without_code_column(self, regime):
        """缺 '代碼' 欄 → 原樣回傳，不炸（上游契約變更時降級而非崩潰）。"""
        _in = pd.DataFrame({"其他": [1, 2]})
        _out, _ = _apply_bear_market_filter(
            _in, "", regime=regime, rs_rows=_rs(("2330", True)))
        assert len(_out) == 2


# ════════════════════════════════════════════════════════════════════
# 5. 設計守衛：不得回退成改 beat_only
# ════════════════════════════════════════════════════════════════════
class TestDoesNotTouchPercentileSemantics:

    _REL = "src/services/fundamental_screener_service.py"

    def test_rs_scan_still_uses_full_pool(self):
        """`run_rs_leader_scan` 的 `beat_only` 必須維持**字面 False**。

        它決定百分位分母；一旦改成由 regime 控制，落後股會因 RS「缺料」
        而被排除在綜合分平均之外 —— 若 RS 原本在拖累它們，分數反而上升。
        見本檔 module docstring。

        走 AST：本檔與受測檔的註解都大量出現 `beat_only` 字樣，
        字串掃描 = 保證假紅燈（同 test_f2_app_decomposition.py 原則 #2）。
        """
        _tree = ast.parse((REPO_ROOT / self._REL).read_text(encoding="utf-8"))
        _bad: list[str] = []
        for _n in ast.walk(_tree):
            if not isinstance(_n, ast.Call):
                continue
            _fn = _n.func
            _name = getattr(_fn, "id", None) or getattr(_fn, "attr", None)
            if _name != "run_rs_leader_scan":
                continue
            for _kw in _n.keywords:
                if _kw.arg != "beat_only":
                    continue
                if not (isinstance(_kw.value, ast.Constant) and _kw.value.value is False):
                    _bad.append(f"line {_n.lineno}: beat_only 不再是字面 False")
        assert not _bad, (
            "run_rs_leader_scan 的 beat_only 被改動：\n  " + "\n  ".join(_bad)
            + "\n→ 那會改變百分位分母，讓空頭濾網變成『幫落後股加分』。"
              "濾網請維持在 _apply_bear_market_filter 做後濾。"
        )

    def test_uses_l0_ssot_for_defensive_regimes(self):
        """防禦性 regime 集合必須引用 L0 SSOT，不得自立常數（§3.3）。"""
        _tree = ast.parse((REPO_ROOT / self._REL).read_text(encoding="utf-8"))
        _names: set[str] = set()
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.ImportFrom) and _n.module == "shared.position_throttle":
                _names.update(a.name for a in _n.names)
        assert "THROTTLE_VETO_REGIMES" in _names, (
            "未從 shared.position_throttle 取用 THROTTLE_VETO_REGIMES —— "
            "自己列 {'bear','caution'} 會與 regime_arbiter.py:66 的定義漂移"
        )
