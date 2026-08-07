"""tests/test_b6b_screener_audit.py — B6-b 選股網三 screener 稽核修正（2026-08）。

全部是**行為斷言**（建構輸入 → 呼叫函式 → 驗結果），沒有原始碼字串掃描守衛：
本 session 已被「照抄實作字面」的字串守衛擋過 7 次假紅燈，且那種守衛永遠發現不了
實作本身有問題。唯一兩處碰到字串的地方（RS 因子 label）也是**先用行為證明舊文案
是假承諾**，再斷言那句假承諾不存在，而不是斷言新文案長什麼樣。

涵蓋 6 條修正：
  F1 缺貨:季序對齊 —— t-1 / t-4 / TTM 四季改用「季序」取，不用 list 位置
     （季序列有洞時位置 4 ≠ 去年同季，會靜默拿錯基期算 YoY）。
  F2 跨季轉強:favorable_of == 0（零證據）不再放 {sid: 0} 假讀數進因子。
  F3 get_ranked_picks:綜合分 None（從未被評分）的檔不再混進「綜合評分排序」結果
     → 不會被 `.head(20)` 凍結進前進式驗證紀錄。
  F4 因子實際覆蓋率揭露（缺貨深掃只覆蓋部分存活池時，原本畫面完全沒提示）。
  F5 RS 因子 label 的假承諾（判定式沒有「贏過大盤」的門檻）。
  F8 前進式驗證:抓不到現價被剔除的檔數 = 對帳端存活者偏誤，須攤在 overall。
  F9 TWSE PE / 名稱 map:不再因「沒有殖利率」連坐丟掉整檔（≈24% 上市股）。
"""
from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.compute.screener.shortage_screener import score_shortage
from src.services.fundamental_screener_service import (
    SCREEN_ANGLE_LABELS,
    composite_rank_candidates,
    get_ranked_picks,
)


# ════════════════════════════════════════════════════════════════
# 共用工廠
# ════════════════════════════════════════════════════════════════
def _q(label, *, rev=1000.0, gp=500.0, cogs=500.0, cl=None, inv=400.0) -> dict:
    """單季 dict。label=None → 不放 label 欄（模擬無法定序 → 退回位置索引）。"""
    _out = {"revenue": rev, "gross_profit": gp, "cogs": cogs,
            "contract_liab": cl, "inventory": inv}
    if label is not None:
        _out["label"] = label
    return _out


def _stock(quarters, **over) -> dict:
    base = {"stock_id": "9999", "name": "測試", "is_finance": False,
            "quarters": quarters, "revenue_yoy_last3": [1.0, 1.0, 1.0]}
    base.update(over)
    return base


def _surv(ids, eps=None) -> pd.DataFrame:
    return pd.DataFrame({"stock_id": list(ids),
                         "eps": list(eps) if eps is not None else [1.0] * len(ids)})


# ════════════════════════════════════════════════════════════════
# F1 缺貨:季序對齊（不用 list 位置當季距）
# ════════════════════════════════════════════════════════════════
# 兩組資料「數值完全相同」，只差第 5 列的季別 label：
#   連續版  : ...2024Q2, **2024Q1**, 2023Q4  → 位置 4 == 去年同季 → YoY 100% → 滿分
#   有洞版  : ...2024Q2, **2023Q4**, 2023Q3  → 去年同季(2024Q1)不存在 → 不該算 YoY
# 若判定式仍用位置索引，兩組會得到**相同**結果（都拿到 100% 的假 YoY）。
def _cl_quarters(fifth_label: str, sixth_label: str, *, labelled: bool = True):
    _labs = ["2025Q1", "2024Q4", "2024Q3", "2024Q2", fifth_label, sixth_label]
    _cls = [200.0, 199.0, 199.0, 199.0, 100.0, 100.0]
    return [_q(_labs[i] if labelled else None, cl=_cls[i]) for i in range(6)]


def test_contract_liab_yoy_uses_real_prior_year_quarter():
    """連續季序：位置 4 == 2024Q1 == 去年同季 → YoY 100% → 合約負債滿分（對照組）。"""
    r = score_shortage(_stock(_cl_quarters("2024Q1", "2023Q4")))
    assert r.metrics["cl_yoy"] == pytest.approx(100.0, abs=0.1)
    assert r.c1_contract_liab > 0.0


def test_contract_liab_yoy_not_faked_when_prior_year_quarter_missing():
    """同一組數值、只是 2024Q1 缺席 → 不可拿 2023Q4 冒充去年同季（§1 不造假）。"""
    r = score_shortage(_stock(_cl_quarters("2023Q4", "2023Q3")))
    assert r.metrics["cl_yoy"] is None, "缺去年同季卻算出 YoY = 拿錯基期"
    assert r.c1_contract_liab == 0.0
    assert r.metrics["quarter_aligned"] is True


def test_contract_liab_positional_fallback_when_quarters_unlabelled():
    """季別無 label / date 可定序 → 退回位置索引（舊行為），不因新邏輯把資料判死。"""
    r = score_shortage(_stock(_cl_quarters("2023Q4", "2023Q3", labelled=False)))
    assert r.metrics["quarter_aligned"] is False
    assert r.metrics["cl_yoy"] == pytest.approx(100.0, abs=0.1)   # 位置 4 → 100.0


def test_quarter_ordinal_accepts_date_when_label_absent():
    """無 label 但有 date（L1 fetcher 兩欄都給）→ 仍以季序對齊。"""
    _dates = ["2025-03-31", "2024-12-31", "2024-09-30",
              "2024-06-30", "2023-12-31", "2023-09-30"]   # 2024-03-31 缺席
    _cls = [200.0, 199.0, 199.0, 199.0, 100.0, 100.0]
    qs = [{**_q(None, cl=_cls[i]), "date": _dates[i]} for i in range(6)]
    r = score_shortage(_stock(qs))
    assert r.metrics["quarter_aligned"] is True
    assert r.metrics["cl_yoy"] is None


def test_dio_ttm_requires_four_real_consecutive_quarters():
    """存貨天數的 TTM 成本必須是**四個真實季**；中間缺季 → None，不拿更早季湊數。"""
    _labs = ["2025Q1", "2024Q4", "2024Q2", "2024Q1", "2023Q4", "2023Q3"]  # 缺 2024Q3
    qs = [_q(lab, cl=100.0) for lab in _labs]
    r = score_shortage(_stock(qs))
    assert r.metrics["dio_t"] is None, "TTM 視窗有洞卻算得出 DIO = 拿錯季湊 4 季"
    assert r.c3_inventory_days == 0.0
    # 對照：季序補齊 → 同樣數值就算得出來（證明差異來自季序，不是數值）
    _full = [_q(lab, cl=100.0) for lab in
             ["2025Q1", "2024Q4", "2024Q3", "2024Q2", "2024Q1", "2023Q4"]]
    r2 = score_shortage(_stock(_full))
    assert r2.metrics["dio_t"] is not None


def test_gross_margin_yoy_also_quarter_aligned():
    """毛利率 YoY 與合約負債走同一套季序對齊（不會只修一半）。"""
    _labs = ["2025Q1", "2024Q4", "2024Q3", "2024Q2", "2023Q4", "2023Q3"]  # 缺 2024Q1
    qs = [_q(lab, gp=600.0 if i == 0 else 500.0, cl=100.0) for i, lab in enumerate(_labs)]
    r = score_shortage(_stock(qs))
    assert r.metrics["gm_t"] == pytest.approx(60.0)
    assert r.metrics["gm_t4"] is None, "缺去年同季卻算得出 gm_t4"


# ════════════════════════════════════════════════════════════════
# F2 跨季轉強:零證據不再變成一個「最差」的假分數
# ════════════════════════════════════════════════════════════════
def _trend_df(rows):
    return pd.DataFrame(rows, columns=["stock_id", "favorable_count", "favorable_of"])


def test_build_trend_map_omits_zero_evidence_stocks(monkeypatch):
    """favorable_of == 0（四個趨勢因子全 NaN）→ 不放 key，不是放 0。"""
    from src.services import fundamental_screener_service as fss
    monkeypatch.setattr(fss, "get_cross_quarter_trends",
                        lambda **_kw: _trend_df([("A", 4, 4), ("B", 0, 4), ("C", 0, 0)]))
    _m = fss.build_trend_map()
    assert _m == {"A": 4, "B": 0}, "零證據的 C 不該帶著捏造的 0 分進因子"


def test_zero_evidence_stock_gets_blank_trend_score_not_lowest(monkeypatch):
    """接到 composite：零證據股的『跨季分』是空白，不是全場最低分。"""
    from src.services import fundamental_screener_service as fss
    monkeypatch.setattr(fss, "get_cross_quarter_trends",
                        lambda **_kw: _trend_df([("A", 4, 4), ("B", 2, 4), ("C", 0, 0)]))
    df, _ = composite_rank_candidates(
        _surv(["A", "B", "C"]), factors=["trend"], trend_map=fss.build_trend_map())
    _c = df[df["代碼"] == "C"]["跨季分"].iloc[0]
    assert _c is None or _c != _c, "零證據股拿到了真實百分位分（捏造值參與排序）"
    assert df[df["代碼"] == "A"]["跨季分"].iloc[0] == 100.0


def test_trend_map_survives_legacy_schema_without_favorable_of(monkeypatch):
    """舊 schema（無 favorable_of 欄）→ 保守全收，不靜默丟資料。"""
    from src.services import fundamental_screener_service as fss
    monkeypatch.setattr(
        fss, "get_cross_quarter_trends",
        lambda **_kw: pd.DataFrame({"stock_id": ["A", "B"], "favorable_count": [3, 0]}))
    assert fss.build_trend_map() == {"A": 3, "B": 0}


# ════════════════════════════════════════════════════════════════
# F3 get_ranked_picks:沒被評分的檔不得混進「綜合評分排序」結果
# ════════════════════════════════════════════════════════════════
def _gated_args():
    """3 檔存活池、2 因子；RS 只覆蓋 A → B/C 只有 1/2 因子 → 涵蓋門檻擋下（綜合分 None）。"""
    return dict(survivors_df=_surv(["A", "B", "C"], [3.0, 2.0, 1.0]),
                rs_rows=[{"代碼": "A", "RS(σ)": 1.0}], auto_fetch=False)


def test_get_ranked_picks_excludes_unscored_picks():
    cands, note = get_ranked_picks(["eps_high", "rs_leader"], top_n=20, **_gated_args())
    assert list(cands["代碼"]) == ["A"], "未取得綜合分的檔仍出現在同源選股結果"
    assert cands["綜合分"].notna().all()
    assert "已排除於名單外" in note


def test_get_ranked_picks_head_n_never_yields_unscored_freeze_rows():
    """凍結路徑取 head(N)：即使 N 大於「有分的檔數」，也不該補進沒分的檔。"""
    cands, _ = get_ranked_picks(["eps_high", "rs_leader"], top_n=300, **_gated_args())
    _top20 = cands.head(20)
    assert len(_top20) == 1
    assert _top20["綜合分"].notna().all()


def test_composite_direct_call_keeps_legacy_show_ranked_last_behaviour():
    """`composite_rank_candidates` 直呼（預設 drop_unscored=False）行為不變：
    沒分的檔仍列出、排最後、綜合分空白 —— 與上面兩條不衝突（不同入口、不同契約）。"""
    df, _ = composite_rank_candidates(
        _surv(["A", "B", "C"], [3.0, 2.0, 1.0]), factors=["eps_high", "rs_leader"],
        rs_rows=[{"代碼": "A", "RS(σ)": 1.0}])
    assert len(df) == 3
    assert df.iloc[0]["代碼"] == "A"
    assert df["綜合分"].isna().sum() == 2


# ════════════════════════════════════════════════════════════════
# F4 因子實際覆蓋率揭露（§5）
# ════════════════════════════════════════════════════════════════
def test_partial_factor_coverage_is_disclosed():
    """缺貨只掃到 2/5（深掃上限）→ note 必須講出實際覆蓋分母。"""
    df, note = composite_rank_candidates(
        _surv(["A", "B", "C", "D", "E"]),
        factors=["eps_high", "shortage"],
        shortage_rows=[{"代碼": "A", "缺貨分數": 80}, {"代碼": "B", "缺貨分數": 20}])
    assert "因子實際覆蓋" in note
    assert "缺貨分 2/5" in note
    assert "EPS分" not in note.split("因子實際覆蓋")[1]  # 全覆蓋的因子不列


def test_full_coverage_no_disclosure_noise():
    df, note = composite_rank_candidates(_surv(["A", "B"], [2.0, 1.0]),
                                         factors=["eps_high"])
    assert "因子實際覆蓋" not in note and note == ""


# ════════════════════════════════════════════════════════════════
# F5 RS 因子:判定式沒有「贏過大盤」門檻 → label 不得如此承諾
# ════════════════════════════════════════════════════════════════
def _rs_frames(n: int = 60):
    """大盤強漲 + 個股微漲 → 個股必然輸給大盤（excess < 0），大盤日報酬 σ > 0。"""
    _idx = pd.date_range("2025-01-01", periods=n, freq="D")
    _m, _mv = 100.0, []
    for i in range(n):
        _mv.append(_m)
        _m *= 1.015 if i % 2 == 0 else 1.005          # 交錯 → σ 非 0
    _sv = [100.0 + 0.05 * i for i in range(n)]        # 幾乎走平
    return (pd.DataFrame({"close": _sv}, index=_idx),
            pd.DataFrame({"close": _mv}, index=_idx))


def test_rs_factor_admits_stocks_that_lost_to_the_market():
    """行為證明：beat_only=False（綜合評分實際用的參數）會把『輸給大盤』的股排進榜。"""
    from src.compute.screener.rs_leader_screener import rank_rs_leaders, to_rows
    _ds, _dm = _rs_frames()
    _rows = to_rows(rank_rs_leaders(
        [{"stock_id": "A", "name": "", "df": _ds}], _dm, lookback=30, beat_only=False))
    assert len(_rows) == 1
    assert _rows[0]["贏過大盤"] is False
    assert _rows[0]["超額%"] < 0
    # 且這種列會被綜合評分當成有效 RS 資料 → 給到 100 分
    df, _ = composite_rank_candidates(_surv(["A"]), factors=["rs_leader"], rs_rows=_rows)
    assert df.iloc[0]["RS分"] == 100.0


def test_rs_angle_label_drops_the_false_beat_market_promise():
    """承上：既然判定式不保證贏大盤，label 就不能寫「仍贏大盤」。

    只斷言那句**已被行為證偽的舊承諾**不存在，不釘新文案長相（避免守衛照抄實作）。
    """
    _label = {v: k for k, v in SCREEN_ANGLE_LABELS.items()}["rs_leader"]
    assert "仍贏大盤" not in _label
    assert "抗跌 RS" in _label          # 既有 test_screener_copy_fix 的契約不破


# ════════════════════════════════════════════════════════════════
# F8 前進式驗證:對帳端存活者偏誤必須攤開
# ════════════════════════════════════════════════════════════════
def _picks(rows):
    return pd.DataFrame(rows, columns=["cohort", "stock_id", "entry_price"])


def test_delisted_pick_counted_and_disclosed():
    """凍結後下市（抓不到現價）→ 剔除數要進 overall + note 明講偏誤方向。"""
    from src.compute.screener.forward_test import reconcile_forward_test
    picks = _picks([("2026-01-01", "A", 100.0), ("2026-01-01", "B", 100.0),
                    ("2026-01-01", "DEAD", 100.0)])
    df, overall = reconcile_forward_test(
        picks, {"A": 120.0, "B": 110.0}, benchmark_returns={"2026-01-01": 0.05})
    assert int(df.iloc[0]["n_dropped"]) == 1
    assert overall["n_dropped_total"] == 1
    assert "存活者偏誤" in overall["note"]
    # 平均報酬只用活著的兩檔（+20% / +10%）→ 15%，證明下市檔真的沒被計入
    assert df.iloc[0]["avg_return_pct"] == pytest.approx(15.0)


def test_no_dropped_picks_no_survivorship_warning():
    from src.compute.screener.forward_test import reconcile_forward_test
    picks = _picks([("2026-01-01", "A", 100.0), ("2026-01-01", "B", 100.0),
                    ("2026-01-01", "C", 100.0)])
    _, overall = reconcile_forward_test(
        picks, {"A": 110.0, "B": 110.0, "C": 110.0},
        benchmark_returns={"2026-01-01": 0.05})
    assert overall["n_dropped_total"] == 0
    assert "存活者偏誤" not in overall["note"]


def test_missing_benchmark_cohorts_are_counted():
    """0050 序列涵蓋不到的凍結批（如超過 1 年前）→ 不該靜默從『平均超額』消失。"""
    from src.compute.screener.forward_test import reconcile_forward_test
    picks = _picks([("2024-01-01", "A", 100.0), ("2024-01-01", "B", 100.0),
                    ("2026-01-01", "C", 100.0), ("2026-01-01", "D", 100.0)])
    _, overall = reconcile_forward_test(
        picks, {"A": 110.0, "B": 110.0, "C": 110.0, "D": 110.0},
        benchmark_returns={"2026-01-01": 0.05})       # 2024 那批沒有基準
    assert overall["n_cohorts_no_bench"] == 1
    assert "無 0050 同期基準" in overall["note"]


# ════════════════════════════════════════════════════════════════
# F9 TWSE 估值 / 名稱 map:未配息股不再被連坐丟掉
#
# ⚠️ E2(2026-08)搬遷後的 patch 目標 —— 這段踩過坑,勿回退：
#   三個 fetcher 已從 `src/ui/tabs/yield_screener.py`(L5)下沉到
#   `src/data/stock/yield_pe_fetcher.py`(L1);`yield_screener` 只剩 re-export。
#   `fetch_pe_name_maps` 在**呼叫時**從 **L1 模組的 globals** 取兩個 fetcher,所以
#     patch.object(yield_screener, "fetch_tpex_yield_pe")   ← 打不到(只改別名綁定)
#     patch("src.services.yield_screener_service.proxy_fetch_url")  ← 打不到(L1 不再繞 L3)
#   兩者都會讓測試「照樣綠」但實際去打真網路 = 最惡劣的假綠燈。
#   下面每個 mock 都額外斷言 **被呼叫過**(call_count / call_args),patch 若沒生效
#   會在那條斷言炸掉,而不是靜默通過。
# ════════════════════════════════════════════════════════════════
@pytest.fixture()
def _clear_pe_caches():
    """清 L1 fetcher 的 @st.cache_data,避免 case 間串擾。"""
    from src.data.stock import yield_pe_fetcher as ypf
    def _clear():
        for _fn in ("fetch_twse_yield_pe", "fetch_tpex_yield_pe"):
            try:
                getattr(ypf, _fn).clear()
            except Exception:
                pass
    _clear()
    yield
    _clear()


def _resp(payload):
    _r = MagicMock()
    _r.status_code = 200
    _r.json.return_value = payload
    return _r


# 取自 2026-08-05 BWIBBU_d 實際回應形狀：未配息 → DividendYield 空字串，PE 照給。
_TWSE_RAW = [
    {"Code": "1102", "Name": "亞泥", "DividendYield": "7.06",
     "PEratio": "10.94", "PBratio": "0.65"},
    {"Code": "2514", "Name": "龍邦", "DividendYield": "",
     "PEratio": "7.07", "PBratio": "0.35"},          # 未配息但 PE 最便宜
    {"Code": "1101", "Name": "台泥", "DividendYield": "3.33",
     "PEratio": "", "PBratio": "0.77"},              # 有配息但無 PE
]


def _assert_patches_landed(_http, _tpex):
    """證明兩個 mock 真的被走到（patch 目標打錯 → 這裡炸，而不是靜默打真網路）。"""
    assert _http.call_count == 1, (
        f"proxy_fetch_url mock 被呼叫 {_http.call_count} 次（預期 1）—— "
        "patch 目標沒打到 L1 的 HTTP 出口，這條測試可能正在打真網路"
    )
    assert "openapi.twse.com.tw" in str(_http.call_args), (
        f"proxy_fetch_url 收到的 URL 不是 TWSE BWIBBU：{_http.call_args}"
    )
    assert _tpex.call_count == 1, (
        f"fetch_tpex_yield_pe mock 被呼叫 {_tpex.call_count} 次（預期 1）—— "
        "patch.object 打在 re-export 別名上而非 L1 模組，真 TPEX fetcher 正在被呼叫"
    )


def test_non_dividend_stock_keeps_pe_and_name(_clear_pe_caches):
    from src.data.stock import yield_pe_fetcher as ypf
    with patch.object(ypf, "proxy_fetch_url",
                      return_value=_resp(_TWSE_RAW)) as _http, \
         patch.object(ypf, "fetch_tpex_yield_pe",
                      return_value=pd.DataFrame()) as _tpex:
        pe_map, name_map = ypf.fetch_pe_name_maps()
        _assert_patches_landed(_http, _tpex)
    assert "2514" in pe_map, "未配息的上市股被殖利率 dropna 連坐丟掉了 PE"
    assert math.isclose(pe_map["2514"], 7.07, rel_tol=1e-9)
    assert name_map["2514"] == "龍邦", "未配息的上市股名稱空白"
    assert "1101" not in pe_map          # 無 PE → 不放 key（不是放 0）
    assert name_map["1101"] == "台泥"    # 但名稱照收


def test_non_dividend_stock_actually_reaches_the_valuation_factor(_clear_pe_caches):
    """端到端：修好之後，未配息股在『估值便宜』因子拿得到分（而且是最便宜的那個）。"""
    from src.data.stock import yield_pe_fetcher as ypf
    from src.services.fundamental_screener_service import _percentile_scores
    with patch.object(ypf, "proxy_fetch_url",
                      return_value=_resp(_TWSE_RAW)) as _http, \
         patch.object(ypf, "fetch_tpex_yield_pe",
                      return_value=pd.DataFrame()) as _tpex:
        pe_map, _ = ypf.fetch_pe_name_maps()
        _assert_patches_landed(_http, _tpex)
    _scores = _percentile_scores(["1102", "2514", "1101"], pe_map, higher_better=False)
    assert _scores["2514"] == 100.0
    assert "1101" not in _scores        # 無 PE → 無估值分，不是 0 分


def test_nonpositive_pe_treated_as_missing(_clear_pe_caches):
    """PE = 0 / 負數是「無本益比」，不是「全市場最便宜」（§1 不造假）。"""
    from src.data.stock import yield_pe_fetcher as ypf
    _raw = [{"Code": "AAA", "Name": "零PE", "DividendYield": "1.0",
             "PEratio": "0.00", "PBratio": "1.0"},
            {"Code": "BBB", "Name": "負PE", "DividendYield": "1.0",
             "PEratio": "-3.50", "PBratio": "1.0"},
            {"Code": "CCC", "Name": "正常", "DividendYield": "1.0",
             "PEratio": "12.00", "PBratio": "1.0"}]
    with patch.object(ypf, "proxy_fetch_url",
                      return_value=_resp(_raw)) as _http, \
         patch.object(ypf, "fetch_tpex_yield_pe",
                      return_value=pd.DataFrame()) as _tpex:
        pe_map, _ = ypf.fetch_pe_name_maps()
        _assert_patches_landed(_http, _tpex)
    assert set(pe_map) == {"CCC"}


def test_yield_screener_reexport_is_the_same_object_as_l1(_clear_pe_caches):
    """L5 re-export 與 L1 是同一個物件 —— app.py / 既有 caller 的舊 import 路徑不變。

    同時把「為什麼 patch 要打 L1」釘成行為契約：re-export 只是別名，
    重綁它不會改變 `fetch_pe_name_maps` 內部解析到的函式。
    """
    from src.data.stock import yield_pe_fetcher as ypf
    from src.ui.tabs import yield_screener as ys
    for _fn in ("fetch_twse_yield_pe", "fetch_tpex_yield_pe", "fetch_pe_name_maps"):
        assert getattr(ys, _fn) is getattr(ypf, _fn), f"{_fn} re-export 不是同一物件"

    # 行為證明：patch L5 別名 → L1 內部呼叫**不受影響**（打不到）
    _sentinel = pd.DataFrame({"代碼": ["9999"], "名稱": ["別名"], "本益比": [1.0]})
    with patch.object(ys, "fetch_twse_yield_pe", return_value=_sentinel), \
         patch.object(ypf, "fetch_twse_yield_pe",
                      return_value=pd.DataFrame()) as _real, \
         patch.object(ypf, "fetch_tpex_yield_pe", return_value=pd.DataFrame()):
        pe_map, _ = ypf.fetch_pe_name_maps()
    assert _real.call_count == 1
    assert "9999" not in pe_map, (
        "patch L5 re-export 竟然影響了 L1 內部呼叫 —— 若哪天成立，"
        "上面幾條測試的 patch 目標說明就過期了，請一起更新"
    )


# ════════════════════════════════════════════════════════════════
# 「查了但沒問題」的回歸釘子 —— 防後續改動把已驗證正確的行為改壞
# ════════════════════════════════════════════════════════════════
def test_prescreen_missing_values_fail_closed_not_open():
    """基本面初篩:缺值 → 該項判 False（不是預設 Pass）。§1 綠燈必須代表算過。"""
    from src.compute.screener.fundamental_prescreen import run_fundamental_prescreen
    _cur = pd.DataFrame([{
        "stock_id": "X", "revenue": np.nan, "gross_profit": np.nan,
        "op_income": np.nan, "net_income": np.nan, "eps": np.nan,
        "total_assets": np.nan, "total_liab": np.nan, "current_assets": np.nan,
    }])
    out = run_fundamental_prescreen(_cur, None)
    assert out.iloc[0]["pass_count"] == 0
    assert bool(out.iloc[0]["survivor"]) is False


def test_prescreen_without_prior_year_cannot_produce_survivors():
    """無去年同季 → 三率三升判 False → 不可能有 survivor（不是『略過該項』）。"""
    from src.compute.screener.fundamental_prescreen import run_fundamental_prescreen
    _cur = pd.DataFrame([{
        "stock_id": "X", "revenue": 100.0, "gross_profit": 40.0, "op_income": 20.0,
        "net_income": 10.0, "eps": 2.0, "total_assets": 200.0,
        "total_liab": 50.0, "current_assets": 120.0,
    }])
    out = run_fundamental_prescreen(_cur, None)
    assert bool(out.iloc[0]["pass_three_rise"]) is False
    assert bool(out.iloc[0]["survivor"]) is False
    assert out.iloc[0]["pass_count"] == 3        # 其餘三項確實有算，不是全滅


def test_shortage_dio_annualises_over_a_full_year_not_a_quarter():
    """存貨天數用「近 4 季成本 / 365」年化（§4.1 量綱）——不是單季成本 ×90。"""
    from shared.shortage_screen_thresholds import SHORTAGE_QUARTER_DAYS
    assert SHORTAGE_QUARTER_DAYS == 365.0
    qs = [_q(lab, cogs=100.0, inv=100.0, cl=100.0) for lab in
          ["2025Q1", "2024Q4", "2024Q3", "2024Q2", "2024Q1", "2023Q4"]]
    r = score_shortage(_stock(qs))
    # 存貨 100、近 4 季成本 400 → 每日成本 400/365 → DIO = 100 / (400/365) = 91.25 天
    assert r.metrics["dio_t"] == pytest.approx(91.25, abs=0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
