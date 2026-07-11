"""v19.84 — 第七份外部 review 查證後修復的回歸測試。

修復(查證屬實才修,詳見 STATE.md v19.84):
1. 旌旗 jingqi:刪 pct20/60/120/240 捏造鍵(×0.9/0.8/0.7 無真實依據,全 repo
   0 讀者;§1 寧缺勿假)— jingqi_calc + section_short 兩處 inline 寫入器共 3 站。
2. section_kline_chart 趨勢建議段:新股 MA20/MA100 NaN 原直接進 f-string 顯示
   「MA20 nan」且 classify_trend_4tier NaN 比較落錯層級 → 補 notna 守衛 + 白話引導。
3. data_loader nest_asyncio 死 import 移除(全 repo 0 asyncio 消費者)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

REPO = Path(__file__).resolve().parent.parent

_JQ_EXPECTED_KEYS = {"avg", "pos", "regime", "color", "label", "total", "source"}


class TestJingqiNoFabricatedKeys:
    def _run(self, monkeypatch, df_adl, cl_data=None):
        from src.services import jingqi_calc as J
        _stub = SimpleNamespace(session_state={})
        if cl_data is not None:
            _stub.session_state["cl_data"] = cl_data
        monkeypatch.setattr(J, "st", _stub)
        J.compute_and_store_jingqi(df_adl)
        return _stub.session_state.get("jingqi_info")

    def test_adl_path_no_pct_keys(self, monkeypatch):
        df = pd.DataFrame({"ad_ratio": [55.0, 60.0, 58.0, 62.0, 61.0]})
        info = self._run(monkeypatch, df)
        assert info is not None
        assert set(info) == _JQ_EXPECTED_KEYS, \
            f"jingqi_info 不可再含捏造 pct 鍵,實際: {sorted(info)}"
        assert info["source"] == "ADL"
        assert abs(info["avg"] - 59.2) < 1e-9

    def test_fallback_path_no_pct_keys_and_flagged(self, monkeypatch):
        twii = pd.DataFrame({"close": [100.0, 101.0, 102.0, 101.5, 103.0, 104.0]})
        info = self._run(monkeypatch, None, cl_data={"tw": {"台股加權指數": twii}})
        assert info is not None
        assert set(info) == _JQ_EXPECTED_KEYS
        assert info["source"] == "大盤估算"   # §1:代理估算必須帶旗標

    def test_all_fail_writes_nothing(self, monkeypatch):
        info = self._run(monkeypatch, None, cl_data={"tw": {}})
        assert info is None   # 全敗不寫(誠實顯示未載入,既有 §1 行為)

    def test_no_fabricated_multipliers_in_writers(self):
        """三個寫入站(jingqi_calc + section_short ×2)不可再寫入捏造 pct 鍵。"""
        for rel in ("src/services/jingqi_calc.py", "src/ui/tabs/macro/section_short.py"):
            src = (REPO / rel).read_text(encoding="utf-8")
            assert "'pct60'" not in src and "'pct240'" not in src, \
                f"{rel} 仍在寫入捏造 pct 鍵"


class TestKlineTrendNanGuard:
    def test_notna_guard_present(self):
        src = (REPO / "src/ui/tabs/stock_sections/section_kline_chart.py").read_text(
            encoding="utf-8")
        assert "isna(_km20)" in src and "isna(_km100)" in src
        assert "均線尚未成形" in src

    def test_classify_only_called_on_valid_values(self):
        """classify_trend_4tier 呼叫必須在 NaN 守衛的 else 分支內。"""
        src = (REPO / "src/ui/tabs/stock_sections/section_kline_chart.py").read_text(
            encoding="utf-8")
        _guard_pos = src.find("isna(_km20)")
        _call_pos = src.find("classify_trend_4tier(_kp, _km20, _km100)")
        assert 0 < _guard_pos < _call_pos, "NaN 守衛必須在 classify 呼叫之前"


class TestNestAsyncioRemoved:
    def test_dead_import_gone(self):
        src = (REPO / "src/data/core/data_loader.py").read_text(encoding="utf-8")
        assert "import nest_asyncio" not in src

    def test_no_asyncio_consumers_repo_wide(self):
        """守恆檢查:src/ 下無 asyncio 使用(死 import 移除的前提;若未來引入
        async 程式碼,本測試提醒重新評估 event-loop patch 需求)。"""
        import subprocess
        proc = subprocess.run(
            ["grep", "-rl", "asyncio", str(REPO / "src")],
            capture_output=True, text=True)
        hits = [l for l in proc.stdout.splitlines() if l.endswith(".py")]
        assert hits == [], f"src/ 出現 asyncio 使用,請重新評估: {hits}"
