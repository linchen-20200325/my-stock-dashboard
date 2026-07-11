"""v19.85 — 資料異常實診修復的回歸測試。

修復(user 2026-07-11 實機截圖觸發,詳見 STATE.md v19.85):
1. NDC 景氣燈號 101 天 stale:StockFeel 文章停在 4 月號 → 新增 FinMind
   `TaiwanBusinessIndicator`(官方鏡像,SDK 驗證存在)為 PRIMARY。
2. 出口/PMI 鏈的 FinMind 段打不存在的 dataset `TaiwanEconomicIndicator`
   (SDK 2.0.4 枚舉 + 官方文件皆無)→ 拔除(§3.3 反捏造)。
3. 總經卡「外銷訂單 YoY」實際資料是海關出口 → 正名「台灣出口 YoY」,
   與資料診斷頁同名(原同鍵不同名,使用者對不起來)。
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd

REPO = Path(__file__).resolve().parent.parent

# TaiwanBusinessIndicator 寬表 fixture(欄位契約:FinMind SDK
# data_loader.taiwan_business_indicator;monitoring_color 為不透明字串,
# parser 不解讀只透傳 — 故 fixture 用任意字串即可)
_TBI_ROWS = [
    {"date": "2026-05-01", "leading": 103.0, "coincident": 101.5,
     "lagging": 100.6, "monitoring": 39, "monitoring_color": "red"},
    {"date": "2026-03-01", "leading": 102.1, "coincident": 101.0,
     "lagging": 100.2, "monitoring": 34, "monitoring_color": "green"},
    {"date": "2026-04-01", "leading": 102.6, "coincident": 101.2,
     "lagging": 100.4, "monitoring": 38, "monitoring_color": "yellow-red"},
]


def _mock_resp(payload):
    return SimpleNamespace(status_code=200, json=lambda: payload)


class TestFetchBusinessIndicatorSeries:
    def test_happy_path_sorted_and_typed(self, monkeypatch):
        from src.data.macro import tw_macro as T
        monkeypatch.delenv("FINMIND_TOKEN", raising=False)
        monkeypatch.setattr(
            T, "fetch_url",
            lambda *a, **k: _mock_resp({"msg": "success", "data": _TBI_ROWS}))
        df = T.fetch_business_indicator_series(months_back=97)
        assert df is not None and len(df) == 3
        assert list(df["date"]) == ["2026-03-01", "2026-04-01", "2026-05-01"], "須由舊到新"
        assert float(df["monitoring"].iloc[-1]) == 39.0
        assert str(df["monitoring_color"].iloc[-1]) == "red"
        assert "leading" in df.columns

    def test_empty_data_returns_none(self, monkeypatch):
        from src.data.macro import tw_macro as T
        monkeypatch.setattr(
            T, "fetch_url",
            lambda *a, **k: _mock_resp({"msg": "dataset not exist", "data": []}))
        assert T.fetch_business_indicator_series(months_back=96) is None

    def test_missing_monitoring_column_returns_none(self, monkeypatch):
        from src.data.macro import tw_macro as T
        monkeypatch.setattr(
            T, "fetch_url",
            lambda *a, **k: _mock_resp(
                {"data": [{"date": "2026-05-01", "value": 39}]}))
        assert T.fetch_business_indicator_series(months_back=95) is None

    def test_requests_correct_dataset_name(self, monkeypatch):
        """釘住 dataset 名:必為 TaiwanBusinessIndicator(防回歸打錯名)。"""
        from src.data.macro import tw_macro as T
        seen = {}

        def _spy(url, params=None, **k):
            seen.update(params or {})
            return _mock_resp({"data": _TBI_ROWS})

        monkeypatch.setattr(T, "fetch_url", _spy)
        T.fetch_business_indicator_series(months_back=94)
        assert seen.get("dataset") == "TaiwanBusinessIndicator"


class TestNdcSignalHistoryTbiPrimary:
    def test_tbi_primary_hit_skips_dgtw(self, monkeypatch):
        from src.data.macro import tw_macro as T
        monkeypatch.setattr(
            T, "fetch_business_indicator_series",
            lambda **k: pd.DataFrame(_TBI_ROWS).sort_values("date")
                          .reset_index(drop=True))

        def _boom(*a, **k):
            raise AssertionError("TBI 命中時不應呼叫 dgtw 掃描")

        monkeypatch.setattr(T, "_dgtw_ndc_indicator_series", _boom)
        r = T.fetch_ndc_signal_history(months_back=5)
        assert r["score_latest"] == 39
        assert r["score_prev"] == 38
        assert r["trend"] == [34, 38, 39]
        assert r["date_latest"] == "2026-05-01"
        assert r["source"] == "FinMind:TaiwanBusinessIndicator"
        assert r["color_latest"] == "red"
        assert r["error"] is None

    def test_all_sources_fail_message(self, monkeypatch):
        from src.data.macro import tw_macro as T
        monkeypatch.setattr(T, "fetch_business_indicator_series",
                            lambda **k: None)
        monkeypatch.setattr(T, "_dgtw_ndc_indicator_series",
                            lambda *a, **k: None)
        r = T.fetch_ndc_signal_history(months_back=4)
        assert r["score_latest"] is None
        assert "FinMind-TBI" in (r["error"] or "")


class TestNdcBlockPlanZero:
    def _clear_block_cache(self):
        from src.data.macro import macro_snapshot as M
        try:
            M.fetch_ndc_block.clear()
        except Exception:
            pass

    def test_block_returns_official_score_and_color(self, monkeypatch):
        from src.data.macro import tw_macro as T
        from src.data.macro import macro_snapshot as M
        self._clear_block_cache()
        monkeypatch.setattr(
            T, "fetch_business_indicator_series",
            lambda **k: pd.DataFrame(_TBI_ROWS).sort_values("date")
                          .reset_index(drop=True))
        out = M.fetch_ndc_block()
        sig = out.get("ndc_signal")
        assert sig, f"應命中方案0,得到 {out}"
        assert sig["score"] == 39
        assert sig["signal"] == "red"
        assert sig["date"] == "2026-05-01"
        assert sig["source"] == "FinMind:TaiwanBusinessIndicator"
        self._clear_block_cache()

    def test_block_sanity_rejects_out_of_range(self, monkeypatch):
        """分數超出 [9,45] → 方案0 跳過,落到後續源(此處全 mock 失敗 → _err_ndc 三源)。"""
        from src.data.macro import tw_macro as T
        from src.data.macro import macro_snapshot as M
        import src.data.proxy as P
        self._clear_block_cache()
        monkeypatch.setattr(
            T, "fetch_business_indicator_series",
            lambda **k: pd.DataFrame(
                [{"date": "2026-05-01", "monitoring": 88,
                  "monitoring_color": "x"}]))
        monkeypatch.setattr(P, "fetch_url", lambda *a, **k: None)
        out = M.fetch_ndc_block()
        assert "ndc_signal" not in out
        assert "三源" in out.get("_err_ndc", "")
        self._clear_block_cache()


class TestFakeDatasetRemoval:
    def test_no_fake_dataset_param_in_chain_files(self):
        """出口鏈 + PMI 鏈 + tw_macro 不得再以 TaiwanEconomicIndicator 作為請求參數。
        (v19.86:原 0-caller 死碼 fetch_pmi_history 已整刪,tw_macro 一併納入掃描)"""
        for rel in ("src/data/macro/macro_snapshot.py",
                    "src/data/macro/macro_core.py",
                    "src/data/macro/tw_macro.py"):
            src = (REPO / rel).read_text(encoding="utf-8")
            assert "'dataset': 'TaiwanEconomicIndicator'" not in src, rel

    def test_fetch_pmi_history_deleted(self):
        """v19.86:fetch_pmi_history 死碼已整刪(0 production caller)。"""
        src = (REPO / "src/data/macro/tw_macro.py").read_text(encoding="utf-8")
        assert "def fetch_pmi_history" not in src

    def test_pmi_registry_is_nine_sources_no_finmind(self):
        from src.data.macro.macro_core import PMI_SOURCE_REGISTRY
        names = [n for n, _ in PMI_SOURCE_REGISTRY]
        assert len(names) == 9, names
        assert "FinMind" not in names
        assert names[0] == "CIER-EN", "優先序首位不變"

    def test_pmi_src_finmind_symbol_gone(self):
        src = (REPO / "src/data/macro/macro_core.py").read_text(encoding="utf-8")
        assert "def _pmi_src_finmind" not in src


class TestExportCardRename:
    def test_section_mid_uses_unified_name(self):
        src = (REPO / "src/ui/tabs/macro/section_mid.py").read_text(encoding="utf-8")
        assert "台灣出口 YoY" in src
        assert "外銷訂單 YoY" not in src.replace(
            "原標題「外銷訂單 YoY」", ""), "卡片/警示/策略字串應全數正名(僅正名註解可留原詞)"

    def test_health_inspector_endpoint_typo_fixed(self):
        src = (REPO / "src/ui/pages/health_inspector.py").read_text(encoding="utf-8")
        assert "XTEXVA01TWM664S" in src
        assert "XTEXVA01TWM657S" not in src
        assert "FinMind-TBI" in src, "NDC 診斷列來源應含 FinMind-TBI"


# ═══ 第八份建議書查證屬實項(同輪併入)══════════════════════════
class TestEighthReviewFixes:
    def test_bollinger_zero_ma_returns_none_not_inf(self):
        """全 0 收盤價(理論邊界):ma=0 → bw 應走 NaN→None,不可回 inf。"""
        import pandas as pd
        from src.compute.strategy.tech_indicators import calc_bollinger
        df = pd.DataFrame({"close": [0.0] * 30})
        assert calc_bollinger(df) is None

    def test_bollinger_normal_path_unaffected(self):
        import pandas as pd
        from src.compute.strategy.tech_indicators import calc_bollinger
        df = pd.DataFrame({"close": [100 + (i % 7) * 0.5 for i in range(40)]})
        out = calc_bollinger(df)
        assert out is not None and out["bw"] == out["bw"]  # not NaN

    def test_mops_branch_gated_on_missing_revenue(self):
        """月營收方案A(MOPS 死 year-file)須以 df_revenue 閘門守住快樂路徑。"""
        src = (REPO / "src/data/core/data_loader.py").read_text(encoding="utf-8")
        assert "range(0 if df_revenue is not None else 3)" in src

    def test_radar_int_cast_guarded(self):
        """五力雷達 int(v) 逐值防護(AI 路徑 LLM 值可能非 int)。"""
        src = (REPO / "src/ui/tabs/tab_stock.py").read_text(encoding="utf-8")
        assert "int(float(_rv_fh))" in src
        assert "_vals = [max(0, min(100, int(v)))" not in src

    def test_trend_score_docstring_no_false_slope_claim(self):
        """趨勢分數 docstring 不得再宣稱未實作的「向上彎折」斜率功能。"""
        src = (REPO / "src/compute/scoring/scoring_engine.py").read_text(encoding="utf-8")
        assert "文實對齊" in src
        # 原句「加入 MA 斜率加分（短均 > 長均 且向上彎折）」不得以宣稱語氣存在
        assert "加入 MA 斜率加分（短均 > 長均 且向上彎折）" not in src

    def test_adl_registry_discloses_proxy_estimate(self):
        """ADL registry 條目須揭露主值為 ^TWII 估算(非真實家數統計)。"""
        src = (REPO / "src/data/core/data_registry.py").read_text(encoding="utf-8")
        assert "^TWII" in src and "估算" in src
